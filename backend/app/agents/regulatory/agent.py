"""규제 에이전트: Tavily → LangChain(OpenAI JSON) 법령명 추출 → 포털 fetch → LangChain 해석."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.core.config import settings
from app.schemas.claim import Claim
from app.schemas.agent_result import RegulatoryAgentOutput, SelectedRegulatoryDocument, RegulatoryEvidenceItem

from app.agents.regulatory.portal_fetch import PortalDocument

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


def _portal_docs_to_validation(docs: list[PortalDocument]) -> list[SelectedRegulatoryDocument]:
    return [
        SelectedRegulatoryDocument(
            law_name=d.law_name,
            primary_url=d.url,
            pdf_url=getattr(d, "pdf_url", "") or "",
            source=d.source,
        )
        for d in docs
    ]


def _mock_output(note: Optional[str] = None) -> RegulatoryAgentOutput:
    return RegulatoryAgentOutput(
        verdict="불명확",
        confidence="MED",
        evidences=[],
        applicable_regulations=["탄소중립기본법 (mock)"],
        incentives=["국내 실증지원 가능성 검토 필요"],
        risks=["해외 인센티브(IRA) 적용 조건 미확정"],
        requires_expert_review=True,
        source_urls=["https://www.law.go.kr"],
        evidence_summary="(mock) 공식 원문 없이 제목·도메인만으로는 적용 여부를 확정할 수 없다.",
        error=note,
        reason=None,
        extracted_law_candidates=[],
        pipeline_notes=[],
        documents_for_validation=[],
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
        evidences=[],
        applicable_regulations=titles,
        incentives=[
            "OPENAI 또는 파이프라인 단계 생략 — 인센티브는 수동 검토",
        ],
        risks=[
            "자동 법령 해석 없음 — 스니펫·제목만으로 법적 확정 불가",
        ],
        requires_expert_review=True,
        source_urls=urls,
        evidence_summary="웹 스니펫·제목 수준의 근거만 있어 적용성은 불명확하며, 공식 법령 원문 대조가 필요하다.",
        error=None,
        reason=None,
        extracted_law_candidates=[],
        pipeline_notes=notes,
        documents_for_validation=[],
    )


def _filter_law_candidates(laws: list[str], claims: list[Claim]) -> list[str]:
    """
    Tavily 스니펫에는 'DAC' 약어가 다른 의미(특히 EU 세무/행정협력 Directive)로 섞여 들어오는 경우가 있다.
    본 프로젝트의 DAC는 Direct Air Capture이므로, 교차검증/보고서 입력을 오염시키는 후보를 제거한다.
    """
    tech_blob = " ".join([c.technology for c in claims]).lower()
    is_direct_air_capture = ("direct air capture" in tech_blob) or ("직접공기포집" in tech_blob) or ("dac" in tech_blob)

    out: list[str] = []
    for raw in laws:
        s = (raw or "").strip()
        if not s:
            continue
        up = s.upper()
        # "DAC6", "DAC7" 같은 약칭은 Direct Air Capture과 무관한 경우가 대부분이라 제거
        if is_direct_air_capture and re.fullmatch(r"DAC\d*", up):
            continue
        # 명시적으로 세무/행정협력 DAC를 가리키는 표현 제거
        if is_direct_air_capture and "ADMINISTRATIVE COOPERATION" in up and "DIRECT AIR" not in up:
            continue
        out.append(s)
    return out[:8]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = (it or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _pick_source_urls(portal_docs: list[PortalDocument], hits_urls: list[str]) -> list[str]:
    """
    source_urls는 '많이'가 아니라 '선별된 근거 링크'여야 한다.
    - 포털/공식 원문 URL을 우선
    - Tavily URL은 상한을 두고 중복 제거
    """
    primary: list[str] = []
    for d in portal_docs:
        if d.url:
            primary.append(d.url)
        if getattr(d, "pdf_url", ""):
            primary.append(getattr(d, "pdf_url", ""))

    picked = _dedupe_keep_order(primary + hits_urls)
    # 보고서/교차검증에서 과도한 링크 나열을 피하기 위해 상한을 낮게 유지
    return picked[:6]


def _ensure_evidence_summary(
    evidence_summary: str,
    *,
    verdict: str,
    confidence: str,
    incentives: list[str],
    risks: list[str],
    source_urls: list[str],
    portal_docs: list[PortalDocument],
) -> str:
    """
    LLM이 evidence_summary를 너무 짧게 내면, 보고서/교차검증에서 쓸 수 있도록 보정한다.
    (팀 문서: 3~6문장 수준의 서술형 요약 권장)
    """
    s = (evidence_summary or "").strip()
    sentence_like = len([x for x in re.split(r"[.!?。]\s*|\n+", s) if x.strip()])
    if len(s) >= 350 and sentence_like >= 3:
        return s

    basis: list[str] = []
    if portal_docs:
        basis.append("정부·공공 포털/공식 문서 텍스트 일부")
    if source_urls:
        basis.append("공식 도메인 링크/스니펫")
    basis_txt = ", ".join(basis) if basis else "웹 스니펫/제목 수준"

    inc = incentives[:2]
    rk = risks[:2]
    inc_txt = "; ".join(inc) if inc else "확정 가능한 인센티브 정보가 제한적"
    risk_txt = "; ".join(rk) if rk else "주요 리스크는 근거 부족/조건 미상"

    return (
        f"수집된 근거({basis_txt})를 바탕으로 적용성을 보수적으로 평가했다. "
        f"현재 판정은 '{verdict}'이며 신뢰도는 {confidence}로, 원문 조문/공식 가이드가 충분히 확보되지 않으면 "
        "규제 적용 여부를 단정할 수 없다는 점을 전제로 한다. "
        f"인센티브 측면에서는 {inc_txt}가 언급되었으나, 적용 요건(규모·연간 톤수·보고/인증 절차 등)은 추가 확인이 필요하다. "
        f"리스크 측면에서는 {risk_txt}가 남아 있으며, 도입·신고·세액공제 가능성은 법무/규제 전문가 검토가 필요하다."
    )


def _safe_str_list(v: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        s = str(x).strip()
        if s:
            out.append(s)
    return out[:limit]


def _analysis_to_evidences(analysis: dict[str, Any]) -> list[RegulatoryEvidenceItem]:
    raw = analysis.get("evidences")
    if not isinstance(raw, list):
        return []
    out: list[RegulatoryEvidenceItem] = []
    for it in raw[:8]:
        if not isinstance(it, dict):
            continue
        out.append(
            RegulatoryEvidenceItem(
                title=str(it.get("title") or "").strip(),
                url=str(it.get("url") or "").strip(),
                pdf_url=str(it.get("pdf_url") or "").strip(),
                source=str(it.get("source") or "").strip(),
                published_at=str(it.get("published_at") or "").strip(),
                summary=str(it.get("summary") or "").strip(),
                excerpt=str(it.get("excerpt") or "").strip(),
                key_point=str(it.get("key_point") or "").strip(),
                conditions=_safe_str_list(it.get("conditions")),
                limitations=_safe_str_list(it.get("limitations")),
                flags=_safe_str_list(it.get("flags")),
                reason=str(it.get("reason") or "").strip(),
            )
        )
    # 비어 있으면 그대로 빈 리스트(후처리로 강제 생성은 하지 않음)
    return [e for e in out if (e.title or e.url or e.summary)]


def _dict_to_output(
    analysis: dict[str, Any],
    law_names: list[str],
    source_urls: list[str],
    pipeline_notes: list[str],
    portal_docs: list[PortalDocument],
) -> RegulatoryAgentOutput:
    ev_sum = analysis.get("evidence_summary")
    picked_urls = _pick_source_urls(portal_docs, source_urls)
    evidences = _analysis_to_evidences(analysis)
    return RegulatoryAgentOutput(
        verdict=_safe_verdict(analysis.get("verdict")),
        confidence=_safe_confidence(analysis.get("confidence")),
        evidences=evidences,
        applicable_regulations=list(analysis.get("applicable_regulations") or [])[:20],
        incentives=list(analysis.get("incentives") or [])[:20],
        risks=list(analysis.get("risks") or [])[:20],
        requires_expert_review=bool(analysis.get("requires_expert_review", True)),
        source_urls=picked_urls,
        evidence_summary=_ensure_evidence_summary(
            str(ev_sum).strip() if ev_sum is not None else "",
            verdict=_safe_verdict(analysis.get("verdict")),
            confidence=_safe_confidence(analysis.get("confidence")),
            incentives=list(analysis.get("incentives") or [])[:20],
            risks=list(analysis.get("risks") or [])[:20],
            source_urls=picked_urls,
            portal_docs=portal_docs,
        ),
        error=None,
        reason=(analysis.get("reason") or None),
        extracted_law_candidates=law_names,
        pipeline_notes=pipeline_notes,
        documents_for_validation=_portal_docs_to_validation(portal_docs),
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
    source_urls = _dedupe_keep_order(source_urls)

    if not (settings.OPENAI_API_KEY or "").strip():
        notes.append("OPENAI_API_KEY 없음 — 2·4단계 생략")
        return _fallback_from_hits_only(
            [h.title for h in hits[:7]],
            source_urls[:10],
            notes,
        )

    law_names, extract_note = await extract_law_candidates(hits)
    if extract_note:
        notes.append(f"법령 추출: {extract_note}")
    if not law_names:
        notes.append("법령명 추출 결과 없음 — Tavily 스니펫만으로 LLM 해석")
        law_names = []
    law_names = _filter_law_candidates(law_names, claims)

    portal_docs, fetch_notes = await fetch_portal_documents(law_names, hits)
    notes.extend(fetch_notes)

    analysis, an_err = await analyze_regulatory_impact(narrative, portal_docs, hits)
    if an_err:
        notes.append(f"해석 단계: {an_err}")

    if analysis is None:
        notes.append("규제 해석 실패 — Tavily 제목 기반 폴백")
        return _fallback_from_hits_only(
            [h.title for h in hits[:7]],
            source_urls[:10],
            notes,
        )

    out = _dict_to_output(analysis, law_names, source_urls, notes, portal_docs)
    return out
