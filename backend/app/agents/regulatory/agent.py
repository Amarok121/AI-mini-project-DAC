"""규제 에이전트: Tavily → 법령명 추출 → 포털 fetch → OpenAI 적용성 평가."""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.schemas.claim import Claim
from app.schemas.agent_result import RegulatoryAgentOutput

from app.agents.regulatory.law_extract import extract_law_candidates
from app.agents.regulatory.portal_fetch import fetch_portal_documents
from app.agents.regulatory.regulatory_llm import analyze_regulatory_impact
from app.agents.regulatory.tavily_search import search_regulations_pipeline


def _claims_narrative(claims: list[Claim]) -> str:
    lines: list[str] = []
    for c in claims:
        lines.append(
            f"- 기술: {c.technology} | 주장: {c.claim} | 적용: {c.application} | 상태: {c.status}"
        )
    return "\n".join(lines) if lines else ""


def _mock_output(note: Optional[str] = None) -> RegulatoryAgentOutput:
    return RegulatoryAgentOutput(
        verdict="불명확",
        confidence="MED",
        applicable_regulations=["탄소중립기본법 (mock)"],
        incentives=["국내 실증지원 가능성 검토 필요"],
        risks=["해외 인센티브(IRA) 적용 조건 미확정"],
        requires_expert_review=True,
        source_urls=["https://www.law.go.kr"],
        error=note,
        reason=None,
        extracted_law_candidates=[],
        pipeline_notes=[],
    )


def _safe_verdict(v: Any) -> str:
    if v in ("해당", "미해당", "불명확"):
        return v
    return "불명확"


def _safe_confidence(v: Any) -> str:
    if v in ("HIGH", "MED", "LOW"):
        return v
    return "MED"


def _fallback_from_hits_only(
    titles: list[str],
    urls: list[str],
    notes: list[str],
) -> RegulatoryAgentOutput:
    return RegulatoryAgentOutput(
        verdict="불명확",
        confidence="MED",
        applicable_regulations=titles,
        incentives=[
            "OPENAI 또는 파이프라인 단계 생략 — 인센티브는 수동 검토",
        ],
        risks=[
            "자동 법령 해석 없음 — 스니펫·제목만으로 법적 확정 불가",
        ],
        requires_expert_review=True,
        source_urls=urls,
        error=None,
        reason=None,
        extracted_law_candidates=[],
        pipeline_notes=notes,
    )


def _dict_to_output(
    analysis: dict[str, Any],
    law_names: list[str],
    source_urls: list[str],
    pipeline_notes: list[str],
) -> RegulatoryAgentOutput:
    return RegulatoryAgentOutput(
        verdict=_safe_verdict(analysis.get("verdict")),
        confidence=_safe_confidence(analysis.get("confidence")),
        applicable_regulations=list(analysis.get("applicable_regulations") or [])[:20],
        incentives=list(analysis.get("incentives") or [])[:20],
        risks=list(analysis.get("risks") or [])[:20],
        requires_expert_review=bool(analysis.get("requires_expert_review", True)),
        source_urls=source_urls[:30],
        error=None,
        reason=(analysis.get("reason") or None),
        extracted_law_candidates=law_names,
        pipeline_notes=pipeline_notes,
    )


async def run(claims: list[Claim]) -> RegulatoryAgentOutput:
    """
    규제 에이전트 (설계 §6.4).

    파이프라인: Tavily → (OpenAI) 법령명 추출 → 포털 fetch → (OpenAI) 적용성·리스크 해석.

    - 공식 규제 문서는 사실로 두고 GRADE 평가는 하지 않음.
    - 보수적으로: 근거 부족 시 불명확 + expert review 권고.
    """
    narrative = _claims_narrative(claims)
    notes: list[str] = []

    if not (settings.TAVILY_API_KEY or "").strip():
        return _mock_output("TAVILY_API_KEY 미설정 — mock 규제 응답 사용")

    try:
        hits = await search_regulations_pipeline(claims, max_results=10)
    except Exception as exc:  # noqa: BLE001
        return _mock_output(f"Tavily 호출 실패: {exc!s}")

    if not hits:
        return _mock_output("Tavily 검색 결과가 비어 있음 (도메인 필터·쿼리 조정 검토)")

    source_urls = [h.url for h in hits if h.url]

    if not (settings.OPENAI_API_KEY or "").strip():
        notes.append("OPENAI_API_KEY 없음 — 2·4단계 생략")
        return _fallback_from_hits_only(
            [h.title for h in hits[:7]],
            source_urls,
            notes,
        )

    law_names, extract_note = await extract_law_candidates(hits)
    if extract_note:
        notes.append(f"법령 추출: {extract_note}")
    if not law_names:
        notes.append("법령명 추출 결과 없음 — Tavily 스니펫만으로 LLM 해석")
        law_names = []

    portal_docs, fetch_notes = await fetch_portal_documents(law_names, hits)
    notes.extend(fetch_notes)

    analysis, an_err = await analyze_regulatory_impact(narrative, portal_docs, hits)
    if an_err:
        notes.append(f"해석 단계: {an_err}")

    if analysis is None:
        notes.append("규제 해석 실패 — Tavily 제목 기반 폴백")
        return _fallback_from_hits_only(
            [h.title for h in hits[:7]],
            source_urls,
            notes,
        )

    out = _dict_to_output(analysis, law_names, source_urls, notes)
    return out
