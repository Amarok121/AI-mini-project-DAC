from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)
from .roadmap_generator import build_adoption_checklist


def _regulatory_section_md(regulatory: RegulatoryAgentOutput) -> str:
    lines = [
        "## 4. 규제·정책 환경 (요약)",
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
    return f"""# 기술 검증·도입 가능성 보고서: {tech}

## 1. Executive Summary
- **초점:** 기술도입 가능성·장기 경제성 관점 (TRL/MRL/CRI는 교차검증·향후 보강).
- 최종 판단: **{cross_validation.overall_verdict}**

## 2. Agent 요약
- Scientific: {scientific.overall_grade} ({scientific.trl_estimate}){f" — GRADE 스켈레톤 가중평균(상위3): {scientific.grade_breakdown.weighted_total}" if scientific.grade_breakdown else ""}
- Industrial: {industrial.overall_level} ({industrial.mrl_estimate})
- Regulatory: {regulatory.verdict} ({regulatory.confidence})

## 3. 도입 체크리스트 (초안)
{checklist}

{reg_md}
"""
