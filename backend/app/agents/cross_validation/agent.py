from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
    ClaimVerificationResult,
)
from app.schemas.claim import ClaimJudgement
from .confidence_scorer import combine_credibility
from .trl_mrl_cri import estimate_cri


def _adapt_claim_verification_result(result: ClaimVerificationResult) -> ClaimJudgement:
    verdict_map = {
        '조건부 가능': '지지',
        '규제 리스크 존재': '반박',
        '판단 보류': '불확실',
    }
    return ClaimJudgement(
        claim_id=result.claim.claim_id,
        judgement=verdict_map.get(result.verdict, '불확실'),
        overall_confidence=result.credibility,
        scientific_confidence=result.credibility,
        industrial_confidence=result.credibility,
        regulatory_confidence='LOW',
        rationale_summary=', '.join(
            [item for item in [result.verdict, result.trl, result.mrl, result.cri, ', '.join(result.flags)] if item]
        ),
        ref_ids=[],
    )


async def run(
    claims: list[Claim],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
) -> CrossValidatorOutput:
    # TODO: 상충 탐지(수치 불일치/단계 불일치/규제충돌) 고도화
    raw_results: list[ClaimVerificationResult] = []
    for claim in claims:
        credibility = combine_credibility(scientific.overall_grade, industrial.overall_level)
        verdict = '조건부 가능' if regulatory.verdict != '미해당' else '규제 리스크 존재'
        flags = [] if regulatory.verdict != '미해당' else ['규제 리스크']
        raw_results.append(
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
    adapted_results = [_adapt_claim_verification_result(result) for result in raw_results]
    return CrossValidatorOutput(
        results=adapted_results,
        overall_verdict='조건부 가능',
        overall_confidence=adapted_results[0].overall_confidence if adapted_results else 'LOW',
        scientific_confidence=adapted_results[0].scientific_confidence if adapted_results else 'LOW',
        industrial_confidence=adapted_results[0].industrial_confidence if adapted_results else 'LOW',
        regulatory_confidence=adapted_results[0].regulatory_confidence if adapted_results else 'LOW',
        conflicts=[],
    )
