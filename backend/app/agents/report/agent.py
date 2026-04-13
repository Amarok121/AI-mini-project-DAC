from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)
from .roadmap_generator import build_adoption_checklist


async def run(
    claims: list[Claim],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
    cross_validation: CrossValidatorOutput,
) -> str:
    # TODO: 템플릿 기반 + 근거 인라인 인용 강화
    tech = claims[0].technology if claims else '기술'
    checklist = '\n'.join([f'- {item}' for item in build_adoption_checklist()])
    return f'''# 기술 검증 보고서: {tech}

## 1. Executive Summary
- 최종 판단: **{cross_validation.overall_verdict}**

## 2. Agent 요약
- Scientific: {scientific.overall_grade} ({scientific.trl_estimate})
- Industrial: {industrial.overall_level} ({industrial.mrl_estimate})
- Regulatory: {regulatory.verdict} ({regulatory.confidence})

## 3. 도입 체크리스트
{checklist}
'''
