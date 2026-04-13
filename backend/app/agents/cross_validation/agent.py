from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
    ClaimVerificationResult,
)
from .confidence_scorer import combine_credibility
from .trl_mrl_cri import estimate_cri


async def run(
    claims: list[Claim],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
) -> CrossValidatorOutput:
    # TODO: 상충 탐지(수치 불일치/단계 불일치/규제충돌) 고도화
    results: list[ClaimVerificationResult] = []
    for claim in claims:
        credibility = combine_credibility(scientific.overall_grade, industrial.overall_level)
        verdict = '조건부 가능' if regulatory.verdict != '미해당' else '규제 리스크 존재'
        flags = [] if regulatory.verdict != '미해당' else ['규제 리스크']
        results.append(
            ClaimVerificationResult(
                claim=claim,
                credibility=credibility,
                verdict=verdict,
                flags=flags,
                trl=scientific.trl_estimate,
                mrl=industrial.mrl_estimate,
                cri=estimate_cri(),
            )
        )
    return CrossValidatorOutput(results=results, overall_verdict='조건부 가능', conflicts=[])
