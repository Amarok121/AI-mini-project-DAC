"""Scientific 에이전트: LangChain LCEL(Runnable)로 SS / OpenAlex / arXiv 검색·병합·GRADE."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from langchain_core.runnables import RunnableLambda, RunnableSequence

from app.schemas.claim import Claim
from app.schemas.agent_result import GradeDimensionScores, ScientificAgentOutput
from app.core.config import settings
from app.schemas.source import SourceItem

from app.agents.scientific.grade_evaluator import (
    average_grade_dimensions,
    normalize_title,
    paper_result_from_parts,
    score_unified_paper,
)
from app.agents.scientific.arxiv import search_preprints
from app.agents.scientific.openalex import search_works
from app.agents.scientific.semantic_scholar import search_papers
from app.agents.scientific.paper_evidence_llm import enrich_papers_evidence_pack
from app.agents.scientific.llm_grade_judge import judge_papers_llm
from app.agents.scientific.pdf_evidence import extract_pdf_evidence_snippet
from app.agents.scientific.query_llm import build_scientific_query_and_keywords_llm

logger = logging.getLogger(__name__)


def _paper_sources_from_results(papers: list[object]) -> list[SourceItem]:
    sources: list[SourceItem] = []
    for paper in papers:
        raw_text = (
            getattr(paper, "excerpt", "") or getattr(paper, "summary", "") or getattr(paper, "abstract", "")
        )
        sources.append(
            SourceItem(
                title=str(getattr(paper, "title", "") or ""),
                authors=list(getattr(paper, "authors", []) or []),
                year=getattr(paper, "year", None) or None,
                source_type="paper",
                url=str(getattr(paper, "url", "") or ""),
                publisher=str(getattr(paper, "journal", "") or ""),
                raw_text=str(raw_text or ""),
            )
        )
    return [source for source in sources if source.title or source.url or source.raw_text]


def _build_search_query(claims: list[Claim]) -> str:
    parts: list[str] = []
    for c in claims:
        parts.append(f"{c.technology} {c.claim} {c.application}")
    base = " ".join(parts).strip()
    anchors = [
        "direct air capture",
        "DAC",
        "carbon capture",
        "CO2 capture",
        "CCUS",
        "sorbent",
        "adsorption",
        "탄소 포집",
        "직접공기포집",
    ]
    # NOTE: 검색 쿼리는 영문 토큰 우선(특히 arXiv)이라, 앵커를 앞에 둬서
    # 'CBAM/IRA/45Q' 같은 규제 토큰이 앞단을 오염시키지 않게 한다.
    q = " ".join(anchors + ([base] if base else [])).strip()
    return q[:500] or "direct air capture review"


def _tech_keywords(claims: list[Claim]) -> list[str]:
    base = [
        "dac",
        "direct air capture",
        "direct air",
        "co2",
        "carbon",
        "capture",
        "ccus",
        "sorbent",
        "adsorption",
        "amine",
        "탄소",
        "직접공기포집",
        "공기포집",
        "흡착",
    ]
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


def _ss_open_access_pdf_url(p: dict[str, Any]) -> str:
    oa = p.get("openAccessPdf")
    if isinstance(oa, dict):
        return str(oa.get("url") or "").strip()
    return ""


def _arxiv_pdf_url(arid: str) -> str:
    a = (arid or "").strip()
    if not a:
        return ""
    return f"https://arxiv.org/pdf/{a}.pdf"


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
                "pdf_url": _ss_open_access_pdf_url(p),
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
                "pdf_url": "",
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
            aid = str(ap.get("arxiv_id") or "").strip()
            if aid and not str(m.get("arxiv_id") or "").strip():
                m["arxiv_id"] = aid
            if aid and not str(m.get("pdf_url") or "").strip():
                m["pdf_url"] = _arxiv_pdf_url(aid)
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
        aid_only = str(ap.get("arxiv_id") or "")
        new_m: dict[str, Any] = {
            "title": str(ap.get("title") or ""),
            "abstract": str(ap.get("abstract") or ""),
            "year": int(ap.get("year") or 0),
            "venue": venue,
            "citations": 0,
            "doi": str(ap.get("doi") or ""),
            "url": str(ap.get("abs_url") or ""),
            "pdf_url": _arxiv_pdf_url(aid_only),
            "semantic_scholar_id": "",
            "openalex_id": "",
            "arxiv_id": aid_only,
            "authors": list(ap.get("authors") or []),
        }
        by_key[key] = new_m
        merged.append(new_m)
    return merged


async def _prepare_inputs(state: dict[str, Any]) -> dict[str, Any]:
    claims = cast(list[Claim], state["claims"])
    fallback_query = _build_search_query(claims)
    fallback_kws = _tech_keywords(claims)
    query, kws = await build_scientific_query_and_keywords_llm(
        claims,
        fallback_query=fallback_query,
        fallback_kws=fallback_kws,
    )
    return {
        **state,
        "query": query,
        "kws": kws,
    }


async def _fetch_sources(state: dict[str, Any]) -> dict[str, Any]:
    q = str(state["query"])
    ss_oa_error: str | None = None
    ss_list: list[dict[str, Any]] = []
    oa_list: list[dict[str, Any]] = []

    # OpenAlex는 키 없이도 안정적이므로 항상 시도 (SS 실패가 OA까지 막지 않게 분리)
    try:
        oa_list = await asyncio.to_thread(lambda: search_works(q, per_page=12))
    except Exception as exc:  # noqa: BLE001
        logger.warning("scientific OpenAlex search failed: %s", exc)
        oa_list = []

    # Semantic Scholar는 키가 없으면 레이트리밋이 잦아 기본 스킵 (있으면만 시도)
    if (settings.SEMANTIC_SCHOLAR_API_KEY or "").strip():
        try:
            ss_list = await asyncio.to_thread(lambda: search_papers(q, limit=12))
        except Exception as exc:  # noqa: BLE001
            logger.warning("scientific Semantic Scholar search failed: %s", exc)
            ss_list = []
    else:
        ss_list = []

    arx_list: list[dict[str, Any]] = []
    try:
        arx_list = await asyncio.to_thread(lambda: search_preprints(q, limit=12))
    except Exception as exc:  # noqa: BLE001
        logger.warning("arXiv search failed: %s", exc)
        arx_list = []

    return {
        **state,
        "ss_list": ss_list,
        "oa_list": oa_list,
        "arx_list": arx_list,
        "ss_oa_error": ss_oa_error,
    }


def _keyword_hits(text: str, kws: list[str]) -> int:
    blob = (text or "").lower()
    hits = 0
    for k in kws:
        kk = (k or "").lower().strip()
        if not kk:
            continue
        if kk in blob:
            hits += 1
    return hits


def _filter_relevant_unified(unified: list[dict[str, Any]], kws: list[str]) -> list[dict[str, Any]]:
    """초록/제목에 기술 키워드가 거의 없는 문서를 제거해 주제 적합도 향상."""
    scored: list[tuple[dict[str, Any], int]] = []
    for u in unified:
        title = str(u.get("title") or "")
        abstract = str(u.get("abstract") or "")
        scored.append((u, _keyword_hits(f"{title}\n{abstract}", kws)))
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored and scored[0][1] <= 0:
        return unified
    return [u for u, h in scored if h >= 1][:25]


async def _assemble_scientific_output(state: dict[str, Any]) -> ScientificAgentOutput:
    q = str(state["query"])
    kws = cast(list[str], state["kws"])
    claims = cast(list[Claim], state["claims"])
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
    unified = _filter_relevant_unified(unified, kws)
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
                pdf_url=str(u.get("pdf_url") or ""),
            )
        )

    papers = await enrich_papers_evidence_pack(papers, claims)

    # Local PDF parsing: extract a small claim-relevant snippet (no LLM).
    claim_text = " ".join([c.claim for c in claims if (c.claim or "").strip()])[:800]
    if claim_text:
        async def _one(p):
            snip = await extract_pdf_evidence_snippet(
                pdf_url=p.pdf_url,
                arxiv_id=p.arxiv_id,
                claim_text=claim_text,
            )
            if not snip:
                return p
            # Keep excerpt for abstract-based evidence-pack; store PDF snippet separately (exclude from API).
            return p.model_copy(update={"pdf_evidence": snip})

        papers = await asyncio.gather(*[_one(p) for p in papers])

    # Final grading is LLM-based (rules + evidence). Heuristic dimensions remain for debugging only.
    judged_papers, overall, judge_note = await judge_papers_llm(papers, claims)
    papers = judged_papers

    avg_dims = average_grade_dimensions([r[2] for r in top[:3]]) if top else GradeDimensionScores()
    mean_score = sum(r[1] for r in top[:3]) / min(3, len(top)) if top else 0.0
    summary = (
        f"상위 {len(papers)}편을 선별한 뒤, LLM 규칙 기반으로 근거 강도를 판정했습니다(근거 인용 포함). "
        f"(참고: 기존 휴리스틱 평균 점수(상위3)≈{mean_score:.2f}) "
        + (f"\n판정 메모: {judge_note}" if judge_note else "")
    )

    return ScientificAgentOutput(
        papers=papers,
        overall_grade=overall,  # type: ignore[arg-type]
        summary=summary,
        error=None,
        grade_breakdown=avg_dims,
        search_sources=sources,
        sources=_paper_sources_from_results(papers),
    )


scientific_chain: RunnableSequence = (
    RunnableLambda(_prepare_inputs)
    | RunnableLambda(_fetch_sources)  # async
    | RunnableLambda(_assemble_scientific_output)
)
