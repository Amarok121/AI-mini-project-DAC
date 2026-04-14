"""
Local PDF evidence extraction (no LLM).

Goal: Extract a small amount of claim-relevant text from a paper PDF so
LLM grading can be based on evidence without sending full PDFs.
"""

from __future__ import annotations

import io
import re
from typing import Optional

import httpx
from pypdf import PdfReader


def _safe_pdf_url(paper_pdf_url: str, *, arxiv_id: str = "") -> str:
    u = (paper_pdf_url or "").strip()
    if u:
        return u
    aid = (arxiv_id or "").strip()
    if aid:
        return f"https://arxiv.org/pdf/{aid}.pdf"
    return ""


def _extract_text_from_pdf_bytes(pdf_bytes: bytes, *, max_pages: int = 12) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks: list[str] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            t = ""
        if t.strip():
            chunks.append(t)
    return "\n".join(chunks)


def _keyword_patterns_from_claim(claim_text: str) -> list[re.Pattern]:
    """
    Build patterns to extract *credibility-relevant* PDF snippets.

    We intentionally bias toward methods/results/validation signals so that
    GRADE dimension scoring is based on what the paper actually evidences,
    not merely whether it mentions a claim keyword.
    """
    c = (claim_text or "").lower()
    pats: list[str] = []

    # Core scientific-method signals (section headings & common phrases)
    pats += [
        r"\babstract\b",
        r"\bintroduction\b",
        r"\bmaterials?\s+and\s+methods\b",
        r"\bmethods?\b",
        r"\bmethodology\b",
        r"\bexperimental\b",
        r"\bexperiments?\b",
        r"\bsetup\b",
        r"\bprotocol\b",
        r"\bprocedure\b",
        r"\bmeasurement(s)?\b",
        r"\bcalibration\b",
        r"\bvalidation\b",
        r"\bbenchmark(ing)?\b",
        r"\buncertainty\b",
        r"\berror\s+(analysis|bar|bars)\b",
        r"\bconfidence\s+interval\b",
        r"\bstatistical\b",
        r"\bresults?\b",
        r"\bdiscussion\b",
        r"\bconclusion(s)?\b",
        r"\blimitation(s)?\b",
        r"\breproducib(le|ility)\b",
        r"\bdata\s+availability\b",
        r"\bcode\s+availability\b",
    ]

    # Modeling/simulation signals (still can be MED if assumptions + validation are explicit)
    pats += [
        r"\bsimulation(s)?\b",
        r"\bmodel(ing)?\b",
        r"\bassumption(s)?\b",
        r"\bsensitivity\b",
        r"\bvalidation\b",
        r"\bverification\b",
        r"\bparameter(s)?\b",
        r"\bobjective\b",
        r"\boptimization\b",
        r"\btechno[-\s]?economic\b",
        r"\bTEA\b",
        r"\bLCA\b",
    ]

    # Domain anchors (helps avoid irrelevant early-page boilerplate)
    pats += [
        r"\bdirect\s+air\s+capture\b",
        r"\bDAC\b",
        r"\bDACCS\b",
        r"\bCO2\b",
        r"\bcarbon\s+(capture|removal)\b",
        r"\bsorbent(s)?\b",
        r"\badsorption\b",
        r"\bdesorption\b",
        r"\bmo(f|fs)\b",
        r"\bmetal[-\s]?organic\s+framework\b",
    ]

    # Claim-related durability/operation hints (secondary)
    pats += [
        r"\bcontinuous\b",
        r"\bcontinuously\b",
        r"\blong[-\s]?term\b",
        r"\bduration\b",
        r"\bstability\b",
        r"\bdurability\b",
        r"\breliability\b",
        r"\bcycle(s|d|ing)?\b",
        r"\bdegradation\b",
        r"\boperat(e|ion|ing)\b",
        r"\btest(ed|ing)?\b",
        r"\bdemonstration\b",
        r"\bpilot\b",
        r"\bfield\b",
        r"\bprototype\b",
        r"\bbench[-\s]?scale\b",
    ]

    # Hour patterns if claim mentions hours/시간
    if any(k in c for k in ("시간", "hour", "hours", "hr", "hrs", "h")):
        pats += [r"\b\d{2,5}\s*(h|hr|hrs|hours)\b", r"\b\d{2,5}\s*hour\b"]

    # Deduplicate patterns while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for p in pats:
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    return [re.compile(p, re.IGNORECASE) for p in uniq]


def _best_snippet(text: str, claim_text: str, *, max_chars: int = 1200) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    pats = _keyword_patterns_from_claim(claim_text)
    # Score windows by number of pattern hits (credibility signals).
    window = 1400
    stride = 700
    best_score = -1
    best_start = 0
    # Limit scanning to avoid huge PDFs; we already cap pages, but still guard.
    scan_limit = min(len(t), 60_000)
    tt = t[:scan_limit]

    for start in range(0, max(1, scan_limit - 1), stride):
        seg = tt[start : min(scan_limit, start + window)]
        score = 0
        for pat in pats:
            if pat.search(seg):
                score += 1
        # Prefer earlier segments when tied (deterministic)
        if score > best_score:
            best_score = score
            best_start = start

    # If we found no signals at all, fall back to the beginning.
    chosen = tt[best_start : min(scan_limit, best_start + window)].strip() if best_score >= 0 else tt[:window].strip()
    if len(chosen) > max_chars:
        chosen = chosen[:max_chars].rstrip()
    suffix = "…" if (best_start + window) < scan_limit else ""
    return chosen + suffix


async def extract_pdf_evidence_snippet(
    *,
    pdf_url: str,
    arxiv_id: str,
    claim_text: str,
    timeout_sec: float = 25.0,
    max_pdf_bytes: int = 8_000_000,
) -> str:
    """
    Download PDF (bounded) and extract a small claim-relevant snippet.
    Returns empty string on failure.
    """
    url = _safe_pdf_url(pdf_url, arxiv_id=arxiv_id)
    if not url:
        return ""
    try:
        async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            content = r.content
    except Exception:  # noqa: BLE001
        return ""
    if not content or len(content) > max_pdf_bytes:
        return ""
    try:
        # Read more pages to increase the chance of capturing Methods/Results sections.
        text = _extract_text_from_pdf_bytes(content, max_pages=12)
    except Exception:  # noqa: BLE001
        return ""
    return _best_snippet(text, claim_text, max_chars=1200)

