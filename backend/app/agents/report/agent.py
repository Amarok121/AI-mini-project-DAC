from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)
from .roadmap_generator import build_adoption_checklist


def _scientific_sources_md(scientific: ScientificAgentOutput) -> str:
    lines: list[str] = [
        "### 3.1 논문·식별자 (Scientific)",
        "",
    ]
    if scientific.error:
        lines.append(f"- _Scientific 단계 오류:_ {scientific.error}")
        lines.append("")
        return "\n".join(lines)
    if not scientific.papers:
        lines.append("- 상위 논문이 없거나 검색 결과가 비어 있습니다.")
        lines.append("")
        return "\n".join(lines)
    for i, p in enumerate(scientific.papers[:15], 1):
        head = f"{i}. **{p.title}**"
        if p.year:
            head += f" ({p.year})"
        lines.append(f"- {head}")
        if p.journal:
            lines.append(f"  - 저널·출처: {p.journal}")
        meta: list[str] = []
        if p.url:
            meta.append(f"[링크]({p.url})")
        if p.doi:
            meta.append(f"DOI: `{p.doi}`")
        if p.arxiv_id:
            meta.append(f"arXiv: `{p.arxiv_id}`")
        if p.openalex_id:
            meta.append(f"OpenAlex: `{p.openalex_id}`")
        if p.semantic_scholar_id:
            meta.append(f"Semantic Scholar: `{p.semantic_scholar_id}`")
        if meta:
            lines.append("  - " + " · ".join(meta))
        if p.summary:
            lines.append(f"  - **요약 (evidence pack):** {p.summary}")
        if p.key_point:
            lines.append(f"  - 핵심: {p.key_point}")
        if p.conditions:
            lines.append(f"  - 조건: {', '.join(p.conditions[:12])}")
        if p.limitations:
            lines.append(f"  - 한계: {', '.join(p.limitations[:12])}")
        if p.excerpt:
            lines.append(f"  - 발췌: _{p.excerpt}_")
        if p.evidence_note:
            lines.append(f"  - 과장 주의: {p.evidence_note}")
        lines.append("")
    return "\n".join(lines)


def _industrial_sources_md(industrial: IndustrialAgentOutput) -> str:
    lines: list[str] = [
        "### 3.2 산업·뉴스 (Industrial)",
        "",
    ]
    if industrial.error:
        lines.append(f"- _Industrial 단계 오류:_ {industrial.error}")
        lines.append("")
        return "\n".join(lines)
    if not industrial.news:
        lines.append("- 뉴스 항목이 없습니다.")
        lines.append("")
        return "\n".join(lines)
    for n in industrial.news[:12]:
        line = f"- **{n.title}**"
        if n.provider:
            line += f" — {n.provider}"
        lines.append(line)
        if n.published_at:
            lines.append(f"  - 일자: {n.published_at}")
        if n.url:
            lines.append(f"  - [링크]({n.url})")
        if n.summary:
            lines.append(f"  - 요약: {n.summary}")
        if n.excerpt:
            lines.append(f"  - 발췌: _{n.excerpt}_")
        if n.flags:
            lines.append(f"  - 플래그: {', '.join(n.flags)}")
        lines.append("")
    if industrial.patents:
        lines.append("#### 특허 (Industrial)")
        lines.append("")
        for pt in industrial.patents[:8]:
            lines.append(f"- **{pt.title}** ({pt.status})")
            if pt.url:
                lines.append(f"  - [링크]({pt.url})")
            if pt.summary:
                lines.append(f"  - 요약: {pt.summary}")
            if pt.key_point:
                lines.append(f"  - 핵심: {pt.key_point}")
            if pt.flags:
                lines.append(f"  - 플래그: {', '.join(pt.flags)}")
            lines.append("")
    return "\n".join(lines)


def _sources_section_md(
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
) -> str:
    return "\n".join(
        [
            "## 3. 근거·출처 (자동 수집)",
            "",
            _scientific_sources_md(scientific),
            _industrial_sources_md(industrial),
        ]
    )


def _regulatory_section_md(regulatory: RegulatoryAgentOutput) -> str:
    lines = [
        "## 5. 규제·정책 환경 (요약)",
        "",
        f"- 적용성 판정: **{regulatory.verdict}** (신뢰도 지표: {regulatory.confidence} — 규제 ‘출처 신뢰’가 아닌 **해석 불확실성** 표시)",
        "",
    ]
    if regulatory.applicable_regulations:
        lines.append("- 관련 규제·문서 후보:")
        for item in regulatory.applicable_regulations[:15]:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.incentives:
        lines.append("- 인센티브·지원 (에이전트 요약):")
        for item in regulatory.incentives:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.risks:
        lines.append("- 리스크:")
        for item in regulatory.risks:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.source_urls:
        lines.append("- 참고 링크:")
        for u in regulatory.source_urls[:12]:
            lines.append(f"  - {u}")
        lines.append("")
    if regulatory.evidence_summary:
        lines.extend(
            [
                "- **규제 근거 팩 (evidence_summary):**",
                "",
                regulatory.evidence_summary,
                "",
            ]
        )
    if regulatory.reason:
        lines.extend(["- **판단 근거 요약 (에이전트):**", "", regulatory.reason, ""])
    if regulatory.extracted_law_candidates:
        lines.append("- 법령·정책명 추출 후보 (2단계):")
        for item in regulatory.extracted_law_candidates[:12]:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.pipeline_notes:
        lines.append("- 파이프라인 메모:")
        for n in regulatory.pipeline_notes[:15]:
            lines.append(f"  - {n}")
        lines.append("")
    if regulatory.error:
        lines.append(f"- _에이전트 메모:_ {regulatory.error}")
        lines.append("")
    return "\n".join(lines)


async def run(
    claims: list[Claim],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
    cross_validation: CrossValidatorOutput,
) -> str:
    # TODO: 템플릿 기반 + 근거 인라인 인용 강화 (설계 §9)
    tech = claims[0].technology if claims else "기술"
    checklist = "\n".join([f"- {item}" for item in build_adoption_checklist()])
    reg_md = _regulatory_section_md(regulatory)
    src_md = _sources_section_md(scientific, industrial)
    return f"""# 기술 검증·도입 가능성 보고서: {tech}

## 1. Executive Summary
- **초점:** 기술도입 가능성·장기 경제성 관점 (TRL/MRL/CRI는 교차검증·향후 보강).
- 최종 판단: **{cross_validation.overall_verdict}**

## 2. Agent 요약
- Scientific: {scientific.overall_grade} ({scientific.trl_estimate}){f" — GRADE 스켈레톤 가중평균(상위3): {scientific.grade_breakdown.weighted_total}" if scientific.grade_breakdown else ""}
- Industrial: {industrial.overall_level} ({industrial.mrl_estimate})
- Regulatory: {regulatory.verdict} ({regulatory.confidence})

{src_md}
## 4. 도입 체크리스트 (초안)
{checklist}

{reg_md}
"""
