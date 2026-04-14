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


def _extract_text_from_pdf_bytes(pdf_bytes: bytes, *, max_pages: int = 6) -> str:
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
    c = (claim_text or "").lower()
    pats: list[str] = []
    # duration / continuous operation hints
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
    # hour patterns if claim mentions hours/시간
    if any(k in c for k in ("시간", "hour", "hours", "hr", "h")):
        pats += [r"\b\d{2,5}\s*(h|hr|hrs|hours)\b", r"\b\d{2,5}\s*hour\b"]
    return [re.compile(p, re.IGNORECASE) for p in pats]


def _best_snippet(text: str, claim_text: str, *, max_chars: int = 1200) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    pats = _keyword_patterns_from_claim(claim_text)
    # Find earliest match among patterns and take a window around it.
    best_pos: Optional[int] = None
    for pat in pats:
        m = pat.search(t)
        if m:
            pos = m.start()
            best_pos = pos if best_pos is None else min(best_pos, pos)
    if best_pos is None:
        # fallback: first chunk (bounded)
        return t[:max_chars] + ("…" if len(t) > max_chars else "")
    start = max(0, best_pos - 400)
    end = min(len(t), best_pos + 800)
    snippet = t[start:end].strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars]
    return snippet + ("…" if end < len(t) else "")


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
        text = _extract_text_from_pdf_bytes(content, max_pages=6)
    except Exception:  # noqa: BLE001
        return ""
    return _best_snippet(text, claim_text, max_chars=1200)

