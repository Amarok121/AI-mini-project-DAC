"""Scientific 에이전트: LangChain LCEL(Runnable)로 SS / OpenAlex / arXiv 검색·병합·GRADE."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from langchain_core.runnables import RunnableLambda, RunnableSequence

from app.schemas.claim import Claim
from app.schemas.agent_result import GradeDimensionScores, ScientificAgentOutput

from app.agents.scientific.grade_evaluator import (
    average_grade_dimensions,
    estimate_trl_from_text,
    normalize_title,
    paper_result_from_parts,
    score_unified_paper,
)
from app.agents.scientific.arxiv import search_preprints
from app.agents.scientific.openalex import search_works
from app.agents.scientific.semantic_scholar import search_papers

logger = logging.getLogger(__name__)


def _build_search_query(claims: list[Claim]) -> str:
    parts: list[str] = []
    for c in claims:
        parts.append(f"{c.technology} {c.claim} {c.application}")
    return " ".join(parts).strip()[:500] or "technology review"


def _tech_keywords(claims: list[Claim]) -> list[str]:
    base = ["dac", "direct air", "co2", "carbon", "capture", "탄소"]
    for c in claims:
        for tok in c.technology.replace(",", " ").split():
            if len(tok) > 1:
                base.append(tok)
    seen: set[str] = set()
    out: list[str] = []
    for b in base:
        low = b.lower()
        if low not in seen:
            seen.add(low)
            out.append(b)
    return out[:24]


def _ss_author_names(p: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for a in p.get("authors") or []:
        if isinstance(a, dict) and a.get("name"):
            names.append(str(a["name"]))
    return names[:15]


def _oa_authors(w: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for auth in w.get("authorships") or []:
        if not isinstance(auth, dict):
            continue
        au = auth.get("author") or {}
        if isinstance(au, dict) and au.get("display_name"):
            names.append(str(au["display_name"]))
    return names[:15]


def _venue_from_ss(p: dict[str, Any]) -> str:
    v = p.get("venue")
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(v.get("name") or "")
    return ""


def _oa_primary_venue(w: dict[str, Any]) -> str:
    pl = w.get("primary_location") or {}
    if not isinstance(pl, dict):
        return ""
    src = pl.get("source") or {}
    if isinstance(src, dict):
        return str(src.get("display_name") or "")
    return ""


def _merge_ss_openalex(ss: list[dict[str, Any]], oa: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ss_keys = {normalize_title(p.get("title") or "") for p in ss}
    oa_by_title = {normalize_title(w.get("title") or ""): w for w in oa}

    merged: list[dict[str, Any]] = []

    for p in ss:
        title = str(p.get("title") or "")
        key = normalize_title(title)
        oa_w = oa_by_title.get(key)
        citations = int(p.get("citationCount") or 0)
        venue = _venue_from_ss(p)
        if oa_w:
            citations = max(citations, int(oa_w.get("cited_by_count") or 0))
            if not venue:
                venue = _oa_primary_venue(oa_w)
        ext = p.get("externalIds") or {}
        doi = ""
        if isinstance(ext, dict):
            doi = str(ext.get("DOI") or "")
        authors = _ss_author_names(p)
        if oa_w and len(authors) < 2:
            authors = _oa_authors(oa_w) or authors

        merged.append(
            {
                "title": title,
                "abstract": str(p.get("abstract") or ""),
                "year": int(p.get("year") or 0),
                "venue": venue,
                "citations": citations,
                "doi": doi,
                "url": str(p.get("url") or ""),
                "semantic_scholar_id": str(p.get("paperId") or ""),
                "openalex_id": str(oa_w.get("id") or "") if oa_w else "",
                "arxiv_id": "",
                "authors": authors,
            }
        )

    for w in oa:
        key = normalize_title(w.get("title") or "")
        if not key or key in ss_keys:
            continue
        merged.append(
            {
                "title": str(w.get("title") or ""),
                "abstract": "",
                "year": int(w.get("publication_year") or 0),
                "venue": _oa_primary_venue(w),
                "citations": int(w.get("cited_by_count") or 0),
                "doi": str(w.get("doi") or "").replace("https://doi.org/", ""),
                "url": str(w.get("id") or ""),
                "semantic_scholar_id": "",
                "openalex_id": str(w.get("id") or ""),
                "arxiv_id": "",
                "authors": _oa_authors(w),
            }
        )

    return merged


def _merge_with_arxiv(
    merged_base: list[dict[str, Any]],
    arx: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(merged_base)
    by_key: dict[str, dict[str, Any]] = {}
    for m in merged:
        by_key[normalize_title(m["title"])] = m

    for ap in arx:
        key = normalize_title(str(ap.get("title") or ""))
        if not key:
            continue
        if key in by_key:
            m = by_key[key]
            ap_abs = str(ap.get("abstract") or "").strip()
            if len(ap_abs) > len(str(m.get("abstract") or "")):
                m["abstract"] = ap_abs
            if ap.get("arxiv_id") and not str(m.get("arxiv_id") or "").strip():
                m["arxiv_id"] = str(ap["arxiv_id"])
            if ap.get("doi") and not str(m.get("doi") or "").strip():
                m["doi"] = str(ap["doi"])
            jr = str(ap.get("journal_ref") or "").strip()
            if jr and not str(m.get("venue") or "").strip():
                m["venue"] = jr
            elif not str(m.get("venue") or "").strip():
                m["venue"] = "arXiv (preprint)"
            if not str(m.get("url") or "").strip() and ap.get("abs_url"):
                m["url"] = str(ap["abs_url"])
            continue
        venue = str(ap.get("journal_ref") or "").strip() or "arXiv (preprint)"
        new_m: dict[str, Any] = {
            "title": str(ap.get("title") or ""),
            "abstract": str(ap.get("abstract") or ""),
            "year": int(ap.get("year") or 0),
            "venue": venue,
            "citations": 0,
            "doi": str(ap.get("doi") or ""),
            "url": str(ap.get("abs_url") or ""),
            "semantic_scholar_id": "",
            "openalex_id": "",
            "arxiv_id": str(ap.get("arxiv_id") or ""),
            "authors": list(ap.get("authors") or []),
        }
        by_key[key] = new_m
        merged.append(new_m)
    return merged


def _prepare_inputs(state: dict[str, Any]) -> dict[str, Any]:
    claims = cast(list[Claim], state["claims"])
    return {
        **state,
        "query": _build_search_query(claims),
        "kws": _tech_keywords(claims),
    }


async def _fetch_sources(state: dict[str, Any]) -> dict[str, Any]:
    q = str(state["query"])
    ss_oa_error: str | None = None
    try:
        ss_list, oa_list = await asyncio.gather(
            asyncio.to_thread(lambda: search_papers(q, limit=10)),
            asyncio.to_thread(lambda: search_works(q, per_page=10)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("scientific SS/OA search failed")
        ss_oa_error = str(exc)
        ss_list, oa_list = [], []

    arx_list: list[dict[str, Any]] = []
    if not ss_oa_error:
        try:
            arx_list = await asyncio.to_thread(lambda: search_preprints(q, limit=10))
        except Exception as exc:  # noqa: BLE001
            logger.warning("arXiv search failed: %s", exc)

    return {
        **state,
        "ss_list": ss_list,
        "oa_list": oa_list,
        "arx_list": arx_list,
        "ss_oa_error": ss_oa_error,
    }


def _assemble_scientific_output(state: dict[str, Any]) -> ScientificAgentOutput:
    q = str(state["query"])
    kws = cast(list[str], state["kws"])
    err = state.get("ss_oa_error")

    if err:
        return ScientificAgentOutput(
            error=f"논문 검색 실패: {err}",
            summary="Semantic Scholar / OpenAlex 호출에 실패했습니다.",
            search_sources=["semantic_scholar", "openalex"],
        )

    ss_list = cast(list[dict[str, Any]], state.get("ss_list") or [])
    oa_list = cast(list[dict[str, Any]], state.get("oa_list") or [])
    arx_list = cast(list[dict[str, Any]], state.get("arx_list") or [])

    if not ss_list and not oa_list and not arx_list:
        return ScientificAgentOutput(
            error=None,
            summary="관련 논문을 찾지 못했습니다. 검색어를 조정해 보세요.",
            search_sources=["semantic_scholar", "openalex", "arxiv"],
        )

    unified = _merge_with_arxiv(_merge_ss_openalex(ss_list, oa_list), arx_list)
    sources = ["semantic_scholar", "openalex", "arxiv"]

    scored: list[tuple[dict[str, Any], float, GradeDimensionScores, str]] = []
    for u in unified[:12]:
        wtot, gd, lvl = score_unified_paper(u, tech_keywords=kws)
        scored.append((u, wtot, gd, lvl))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:7]

    papers = []
    for u, wtot, gd, lvl in top:
        papers.append(
            paper_result_from_parts(
                title=u["title"],
                authors=list(u.get("authors") or []),
                year=int(u.get("year") or 0),
                journal=str(u.get("venue") or ""),
                url=str(u.get("url") or ""),
                grade_score=wtot,
                grade_level=lvl,
                citation_count=int(u.get("citations") or 0),
                abstract=str(u.get("abstract") or ""),
                ss_id=str(u.get("semantic_scholar_id") or ""),
                oa_id=str(u.get("openalex_id") or ""),
                doi=str(u.get("doi") or ""),
                arxiv_id=str(u.get("arxiv_id") or ""),
            )
        )

    avg_dims = average_grade_dimensions([r[2] for r in top[:3]]) if top else GradeDimensionScores()
    mean_score = sum(r[1] for r in top[:3]) / min(3, len(top)) if top else 0.0
    if mean_score >= 0.75:
        overall = "HIGH"
    elif mean_score >= 0.5:
        overall = "MED"
    else:
        overall = "LOW"

    abstract_blob = " ".join(str(u.get("abstract") or "") for u, _, _, _ in top[:3])
    trl = estimate_trl_from_text(abstract_blob + " " + q)

    summary = (
        f"Semantic Scholar·OpenAlex·arXiv 기준 상위 {len(papers)}편을 선별했습니다. "
        f"평균 가중 GRADE 스켈레톤 점수는 상위 3편 기준 약 {mean_score:.2f}이며, "
        "자동 휴리스틱이므로 임상·정책 GRADE와 동일하지 않습니다."
    )

    return ScientificAgentOutput(
        papers=papers,
        overall_grade=overall,  # type: ignore[arg-type]
        trl_estimate=trl,
        summary=summary,
        error=None,
        grade_breakdown=avg_dims,
        search_sources=sources,
    )


scientific_chain: RunnableSequence = (
    RunnableLambda(_prepare_inputs)
    | RunnableLambda(_fetch_sources)  # async
    | RunnableLambda(_assemble_scientific_output)
)
