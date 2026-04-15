from __future__ import annotations

import json
import re
from typing import Any

from app.schemas.agent_result import (
    IndustrialAgentOutput,
    PerformanceGapResult,
    RegulatoryAgentOutput,
    RegulatoryConflictResult,
    ScientificAgentOutput,
)


def build_cross_validation_tools() -> list[dict[str, Any]]:
    """LLM이 최종 교차검증 결과를 단일 구조체로 제출하도록 강제하는 tool schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": "submit_cross_validation_report",
                "description": (
                    "뉴스/특허/규제와 논문 근거를 종합하여 교차검증 결과를 최종 제출한다. "
                    "conflicts, performance_gaps, regulatory_conflicts를 반드시 채운다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conflicts": {
                            "type": "array",
                            "description": (
                                "뉴스/특허 주장 vs 논문 근거의 정합성 판정. "
                                "각 항목은 반드시 한국어로 작성. "
                                "무엇이 맞고/틀린지 + 어떤 출처/문장을 근거로 삼았는지 함께 포함."
                            ),
                            "items": {"type": "string"},
                        },
                        "news_audits": {
                            "type": "array",
                            "description": (
                                "입력된 모든 뉴스를 1건도 누락 없이 평가한 결과. "
                                "각 뉴스마다 제공된 모든 논문 중 가장 관련성 높은 1편을 선택하거나, "
                                "적합 논문이 없으면 matched_paper_title='N/A'로 기록. "
                                "각 항목은 반드시 한국어로 작성."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "news_title": {"type": "string"},
                                    "verdict": {
                                        "type": "string",
                                        "enum": ["지지", "반박", "보완필요"],
                                    },
                                    "reason": {"type": "string"},
                                    "evidence": {"type": "string"},
                                    "matched_paper_title": {
                                        "type": "string",
                                        "description": (
                                            "해당 뉴스 평가에 사용한 논문 제목(입력 scientific.papers 중 1개) "
                                            "또는 적합 논문이 없을 때 'N/A'"
                                        ),
                                    },
                                    "matched_paper_reason": {
                                        "type": "string",
                                        "description": "이 논문을 선택한 이유(핵심 연결고리)",
                                    },
                                },
                                "required": [
                                    "news_title",
                                    "verdict",
                                    "reason",
                                    "evidence",
                                    "matched_paper_title",
                                    "matched_paper_reason",
                                ],
                            },
                        },
                        "performance_gaps": {
                            "type": "array",
                            "description": (
                                "뉴스/특허의 수치형 주장과 논문 실험 수치의 비교 결과. "
                                "수치 비교가 가능한 경우에만 항목 생성. 한국어로 작성."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "metric": {"type": "string"},
                                    "sci_val": {"type": "number"},
                                    "ind_val": {"type": "number"},
                                    "hype_index": {"type": "number"},
                                    "status": {
                                        "type": "string",
                                        "enum": [
                                            "CRITICAL_MISREPRESENTATION",
                                            "Hype Warning",
                                            "Normal",
                                        ],
                                    },
                                    "description": {"type": "string"},
                                    "analyst_note": {
                                        "type": "string",
                                        "description": "비교 근거(논문 제목/뉴스 제목/핵심 문장)를 함께 포함",
                                    },
                                },
                                "required": [
                                    "metric",
                                    "sci_val",
                                    "ind_val",
                                    "hype_index",
                                    "status",
                                    "description",
                                    "analyst_note",
                                ],
                            },
                        },
                        "regulatory_conflicts": {
                            "type": "array",
                            "description": (
                                "규제/특허 vs claim 기술의 정합성 평가. "
                                "규제 적용 여부, 위반 가능성, 특허 문맥 불일치 등을 포함. 한국어로 작성."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "conflict_type": {"type": "string"},
                                    "severity": {
                                        "type": "string",
                                        "enum": ["HIGH", "MED", "LOW"],
                                    },
                                    "description": {"type": "string"},
                                    "analyst_note": {
                                        "type": "string",
                                        "description": "규제/특허 판단 근거가 된 문서명/리스크/핵심 문장을 포함",
                                    },
                                },
                                "required": [
                                    "conflict_type",
                                    "severity",
                                    "description",
                                    "analyst_note",
                                ],
                            },
                        },
                        "tech_status": {
                            "type": "string",
                            "description": "논문 중심으로 평가한 현재 기술 실체/성숙도 요약.",
                        },
                        "final_verdict": {
                            "type": "string",
                            "description": "claim에 대한 최종 판정 요약.",
                        },
                        "is_fake": {
                            "type": "boolean",
                            "description": "허구/왜곡 의심으로 판정하는지 여부.",
                        },
                    },
                    "required": [
                        "conflicts",
                        "news_audits",
                        "performance_gaps",
                        "regulatory_conflicts",
                        "tech_status",
                        "final_verdict",
                        "is_fake",
                    ],
                },
            },
        }
    ]


def parse_cross_validation_tool_calls(
    tool_calls: list[Any],
) -> tuple[list[str], list[dict[str, str]], list[PerformanceGapResult], list[RegulatoryConflictResult], str, str, bool]:
    """
    LLM tool-call 결과를 Cross Validation 내부 모델로 변환.
    반환: (
      conflicts,
      news_audits,
      performance_gaps,
      regulatory_conflicts,
      tech_status,
      final_verdict,
      narrative_fail
    )
    """
    for call in tool_calls or []:
        function = getattr(call, "function", None)
        if function is None or getattr(function, "name", "") != "submit_cross_validation_report":
            continue

        try:
            args = json.loads(function.arguments or "{}")
        except Exception:
            continue

        conflicts = [
            _translate_common_terms(str(item).strip())
            for item in args.get("conflicts", [])
            if str(item).strip()
        ]
        news_audits = []
        for item in args.get("news_audits", []):
            title = _translate_common_terms(str(item.get("news_title", "")).strip())
            verdict = str(item.get("verdict", "")).strip()
            reason = _translate_common_terms(str(item.get("reason", "")).strip())
            evidence = _translate_common_terms(str(item.get("evidence", "")).strip())
            matched_paper_title = _translate_common_terms(str(item.get("matched_paper_title", "")).strip())
            matched_paper_reason = _translate_common_terms(str(item.get("matched_paper_reason", "")).strip())
            if title and verdict and reason and evidence and matched_paper_title and matched_paper_reason:
                news_audits.append(
                    {
                        "news_title": title,
                        "verdict": verdict,
                        "reason": reason,
                        "evidence": evidence,
                        "matched_paper_title": matched_paper_title,
                        "matched_paper_reason": matched_paper_reason,
                    }
                )
        performance_gaps = [
            PerformanceGapResult(**item) for item in args.get("performance_gaps", [])
        ]
        regulatory_conflicts = [
            RegulatoryConflictResult(
                conflict_type=_translate_common_terms(str(item.get("conflict_type", ""))),
                severity=str(item.get("severity", "")),
                description=_translate_common_terms(str(item.get("description", ""))),
                analyst_note=_translate_common_terms(str(item.get("analyst_note", ""))),
            )
            for item in args.get("regulatory_conflicts", [])
        ]
        narrative_fail = bool(args.get("is_fake", False))

        tech_status = _translate_common_terms(str(args.get("tech_status", "")).strip())
        final_verdict = _translate_common_terms(str(args.get("final_verdict", "")).strip())

        return (
            conflicts,
            news_audits,
            performance_gaps,
            regulatory_conflicts,
            tech_status,
            final_verdict,
            narrative_fail,
        )

    return [], [], [], [], "", "", False


def validate_news_audits(news_audits: list[dict[str, str]], industrial: IndustrialAgentOutput) -> tuple[bool, list[str]]:
    """
    입력 뉴스가 누락 없이 평가되었는지 검증.
    """
    expected_titles = [n.title.strip() for n in industrial.news if n.title.strip()]
    submitted_titles = {item.get("news_title", "").strip() for item in news_audits}
    missing = [title for title in expected_titles if title not in submitted_titles]
    return len(missing) == 0, missing


UNMATCHED_PAPER_MARKERS = {"n/a", "none", "없음", "미선정", "미해당"}


def _is_unmatched_paper_title(title: str) -> bool:
    return (title or "").strip().lower() in UNMATCHED_PAPER_MARKERS


def validate_news_audit_paper_titles(
    news_audits: list[dict[str, str]],
    scientific: ScientificAgentOutput,
) -> tuple[bool, list[str]]:
    """
    news_audits의 matched_paper_title이 scientific.papers 내 유효 제목 또는 N/A 계열인지 검증.
    """
    paper_titles = {p.title.strip() for p in scientific.papers if p.title.strip()}
    invalid: list[str] = []
    for item in news_audits:
        title = (item.get("matched_paper_title", "") or "").strip()
        news_title = (item.get("news_title", "") or "").strip()
        if not title:
            invalid.append(f"{news_title}: matched_paper_title 비어 있음")
            continue
        if _is_unmatched_paper_title(title):
            continue
        if title not in paper_titles:
            invalid.append(f"{news_title}: 입력 논문 목록에 없는 matched_paper_title='{title}'")
    return len(invalid) == 0, invalid


def summarize_news_audits(news_audits: list[dict[str, str]]) -> dict[str, float]:
    """
    news_audits의 판정 품질 요약.
    """
    total = len(news_audits)
    if total == 0:
        return {
            "total": 0.0,
            "support_ratio": 0.0,
            "refute_ratio": 0.0,
            "supplement_ratio": 0.0,
            "na_paper_ratio": 0.0,
        }

    support = 0
    refute = 0
    supplement = 0
    na_paper = 0
    for item in news_audits:
        verdict = (item.get("verdict", "") or "").strip()
        matched_title = (item.get("matched_paper_title", "") or "").strip()
        if verdict == "지지":
            support += 1
        elif verdict == "반박":
            refute += 1
        elif verdict == "보완필요":
            supplement += 1
        if _is_unmatched_paper_title(matched_title):
            na_paper += 1

    return {
        "total": float(total),
        "support_ratio": support / total,
        "refute_ratio": refute / total,
        "supplement_ratio": supplement / total,
        "na_paper_ratio": na_paper / total,
    }


def _contains_evidence_marker(text: str) -> bool:
    normalized = text.lower()
    return ("근거:" in text) or ("evidence:" in normalized)


def _contains_english(text: str) -> bool:
    return bool(re.search(r"[A-Za-z][a-z]{2,}", text or ""))


def _translate_common_terms(text: str) -> str:
    # URL/인용 텍스트 손상을 피하기 위해 최소 치환만 적용
    if not text:
        return text
    return re.sub(r"\bclaim\b", "주장", text, flags=re.IGNORECASE)


def report_contains_english(
    conflicts: list[str],
    news_audits: list[dict[str, str]],
    regulatory_conflicts: list[RegulatoryConflictResult],
) -> bool:
    def _strip_citation_chunks(text: str) -> str:
        stripped = re.sub(r"url='[^']*'", "", text or "", flags=re.IGNORECASE)
        stripped = re.sub(r"논문='[^']*'", "", stripped)
        stripped = re.sub(r"뉴스='[^']*'", "", stripped)
        stripped = re.sub(r"규제='[^']*'", "", stripped)
        stripped = re.sub(r"출처='[^']*'", "", stripped)
        stripped = re.sub(r"발췌='[^']*'", "", stripped)
        return stripped

    for item in conflicts:
        if _contains_english(_strip_citation_chunks(item)):
            return True
    for item in news_audits:
        if _contains_english(_strip_citation_chunks(item.get("reason", ""))) or _contains_english(
            _strip_citation_chunks(item.get("evidence", ""))
        ):
            return True
    for item in regulatory_conflicts:
        if _contains_english(_strip_citation_chunks(item.description)) or _contains_english(
            _strip_citation_chunks(item.analyst_note)
        ):
            return True
    return False


def _trim(text: str, limit: int = 140) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))


def _paper_evidence(scientific: ScientificAgentOutput) -> str:
    if not scientific.papers:
        return "논문='N/A'"
    paper = scientific.papers[0]
    return f"논문='{paper.title}' url='{paper.url}'"


def _tokenize_for_overlap(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[A-Za-z가-힣0-9]{3,}", text or "")}


def _extract_acronyms(text: str) -> set[str]:
    return {tok.upper() for tok in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text or "")}


def _paper_to_text(paper) -> str:
    return " ".join(
        [
            paper.title or "",
            paper.summary or "",
            paper.excerpt or "",
            paper.key_point or "",
            paper.reason or "",
            " ".join(paper.conditions or []),
            " ".join(paper.limitations or []),
        ]
    )


def _paper_sort_key_for_fallback(paper: Any) -> tuple[float, float]:
    year = float(getattr(paper, "year", 0) or 0)
    grade = float(getattr(paper, "grade_score", 0.0) or 0.0)
    return (year, grade)


def _find_best_paper_for_news(
    news_text: str,
    scientific: ScientificAgentOutput,
    matched_paper_title: str = "",
    min_overlap_score: int = 2,
) -> Any | None:
    if not scientific.papers:
        return None

    title_norm = (matched_paper_title or "").strip().lower()
    if title_norm:
        for paper in scientific.papers:
            if paper.title.strip().lower() == title_norm:
                return paper
        for paper in scientific.papers:
            if title_norm in paper.title.strip().lower() or paper.title.strip().lower() in title_norm:
                return paper

    news_tokens = _tokenize_for_overlap(news_text)
    if not news_tokens:
        return scientific.papers[0]

    best = scientific.papers[0]
    best_score = -1
    for paper in scientific.papers:
        paper_tokens = _tokenize_for_overlap(_paper_to_text(paper))
        score = len(news_tokens.intersection(paper_tokens))
        if score > best_score:
            best = paper
            best_score = score
    if best_score < min_overlap_score:
        return None
    return best


def _resolve_paper_by_title(scientific: ScientificAgentOutput, matched_paper_title: str) -> Any | None:
    """
    LLM이 선택한 matched_paper_title을 scientific.papers에서 해석.
    유효하지 않으면 None 반환(임의 대체 매칭 금지).
    """
    title = (matched_paper_title or "").strip()
    if not title or _is_unmatched_paper_title(title):
        return None

    title_norm = title.lower()
    for paper in scientific.papers:
        if paper.title.strip().lower() == title_norm:
            return paper
    return None


def select_matched_paper_for_news(
    news_title: str,
    news_summary: str,
    news_excerpt: str,
    scientific: ScientificAgentOutput,
) -> tuple[str, str]:
    """
    뉴스 텍스트와 scientific.papers 전체를 비교해 가장 관련성 높은 논문 제목을 반환.
    충분한 일치 근거가 없으면 ('N/A', 사유) 반환.
    """
    news_text = f"{news_title} {news_summary} {news_excerpt}"

    news_acronyms = _extract_acronyms(news_text)
    paper_acronyms_union: set[str] = set()
    for paper in scientific.papers:
        paper_acronyms_union.update(_extract_acronyms(_paper_to_text(paper)))
    unknown_acronyms = news_acronyms - paper_acronyms_union

    paper = _find_best_paper_for_news(news_text, scientific, "", min_overlap_score=2)
    if paper is not None:
        return paper.title, "뉴스-논문 공통 키워드 및 핵심 문맥 일치로 선택"

    # 키워드 교집합이 약하더라도 약어 문맥이 일관된 경우, 최신/근거점수 기준으로 보조 매칭
    # (예: 뉴스가 한국어 중심일 때 영문 논문과의 표면 토큰 교집합이 낮은 경우)
    if unknown_acronyms:
        return "N/A", "뉴스의 핵심 약어/식별자가 논문 집합과 일치하지 않아 직접 매칭 근거가 부족함"

    if len(news_acronyms) == 1:
        dominant = next(iter(news_acronyms))
        candidates = [
            p
            for p in scientific.papers
            if dominant in _extract_acronyms(_paper_to_text(p))
        ]
        if candidates:
            best = sorted(candidates, key=_paper_sort_key_for_fallback, reverse=True)[0]
            return best.title, "뉴스-논문 약어 문맥은 일치하나 세부 키워드 교집합이 약해 최신 근거 논문으로 보조 매칭"

    return "N/A", "입력된 논문들 중 해당 뉴스와 직접 연결되는 근거가 부족함"


def _news_evidence(news) -> str:
    quote = news.excerpt or news.summary or news.reason
    if _contains_hangul(quote):
        return f"뉴스='{news.title}' url='{news.url}' 발췌='{_trim(quote)}'"
    return f"뉴스='{news.title}' url='{news.url}' 발췌='영문 원문(출처 URL 참조)'"


def build_news_specific_evidence(
    news_title: str,
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    matched_paper_title: str = "",
    matched_paper_reason: str = "",
) -> str:
    target = None
    normalized_title = (news_title or "").strip()
    for news in industrial.news:
        if news.title.strip() == normalized_title:
            target = news
            break
    if target is None and industrial.news:
        target = industrial.news[0]

    news_text = f"{target.title if target else ''} {target.summary if target else ''} {target.excerpt if target else ''}"
    paper = _resolve_paper_by_title(scientific, matched_paper_title)
    if paper is None and not matched_paper_title.strip():
        # 매칭 제목 누락 시 선택 로직을 재사용해 보조 매칭 수행.
        selected_title, _ = select_matched_paper_for_news(
            target.title if target else news_title,
            target.summary if target else "",
            target.excerpt if target else "",
            scientific,
        )
        paper = _resolve_paper_by_title(scientific, selected_title)

    if paper is None:
        paper_text = "논문='N/A'"
        if matched_paper_reason:
            paper_text += f" 선정이유='{_trim(matched_paper_reason)}'"
    else:
        paper_text = f"논문='{paper.title}' url='{paper.url}'"
        if matched_paper_reason:
            paper_text += f" 선정이유='{_trim(matched_paper_reason)}'"
    if target is None:
        return f"{paper_text}; 뉴스='N/A'"
    return f"{paper_text}; {_news_evidence(target)}"


def _base_conflict_evidence(scientific: ScientificAgentOutput, industrial: IndustrialAgentOutput) -> str:
    first_news_title = industrial.news[0].title if industrial.news else ""
    return f"근거: {build_news_specific_evidence(first_news_title, scientific, industrial)}"


def _base_regulatory_evidence(regulatory: RegulatoryAgentOutput) -> str:
    regulations = ", ".join(regulatory.applicable_regulations[:2]) or "N/A"
    risk = _trim(regulatory.risks[0]) if regulatory.risks else "N/A"
    if risk != "N/A" and not _contains_hangul(risk):
        risk = "영문 리스크 원문(출처 URL 참조)"
    source = regulatory.source_urls[0] if regulatory.source_urls else "N/A"
    return f"근거: 규제='{regulations}', 리스크='{risk}', 출처='{source}'"


def enrich_cross_validation_evidence(
    conflicts: list[str],
    regulatory_conflicts: list[RegulatoryConflictResult],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
) -> tuple[list[str], list[RegulatoryConflictResult]]:
    """
    LLM 응답에 근거 문구가 누락된 경우 source 기반 최소 근거를 자동 보강한다.
    판단 자체는 바꾸지 않고 설명 품질만 높인다.
    """
    conflict_evidence = _base_conflict_evidence(scientific, industrial)
    regulatory_evidence = _base_regulatory_evidence(regulatory)

    enriched_conflicts: list[str] = []
    for conflict in conflicts:
        conflict_text = _translate_common_terms(conflict)
        if _contains_evidence_marker(conflict_text):
            enriched_conflicts.append(conflict_text)
            continue

        if conflict_text.startswith("[REG_"):
            enriched_conflicts.append(f"{conflict_text} | {regulatory_evidence}")
        else:
            enriched_conflicts.append(f"{conflict_text} | {conflict_evidence}")

    enriched_regulatory_conflicts: list[RegulatoryConflictResult] = []
    for item in regulatory_conflicts:
        note = _translate_common_terms(item.analyst_note or "")
        if not _contains_evidence_marker(note):
            note = f"{note} | {regulatory_evidence}" if note else regulatory_evidence
        enriched_regulatory_conflicts.append(
            RegulatoryConflictResult(
                conflict_type=_translate_common_terms(item.conflict_type),
                severity=item.severity,
                description=_translate_common_terms(item.description),
                analyst_note=note,
            )
        )

    return enriched_conflicts, enriched_regulatory_conflicts
