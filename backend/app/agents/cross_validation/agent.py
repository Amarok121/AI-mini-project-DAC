from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
    ClaimVerificationResult,
    PaperResult,
    SelectedPaperDocument,
)
from .confidence_scorer import combine_credibility
from .trl_mrl_cri import estimate_cri


def _paper_to_selected(p: PaperResult) -> SelectedPaperDocument:
    if p.semantic_scholar_id and p.arxiv_id:
        src = "merged"
    elif p.arxiv_id:
        src = "arxiv"
    elif p.semantic_scholar_id:
        src = "semantic_scholar"
    elif p.openalex_id:
        src = "openalex"
    else:
        src = ""
    return SelectedPaperDocument(
        title=p.title,
        primary_url=p.url,
        pdf_url=p.pdf_url,
        doi=p.doi,
        semantic_scholar_id=p.semantic_scholar_id,
        openalex_id=p.openalex_id,
        arxiv_id=p.arxiv_id,
        source_system=src,
    )


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
                trl="",
                mrl=industrial.mrl_estimate,
                cri=estimate_cri(),
            )
        )

    papers_for_validation = [_paper_to_selected(p) for p in scientific.papers]
    regulations_for_validation = list(regulatory.documents_for_validation)

    return CrossValidatorOutput(
        results=results,
        overall_verdict='조건부 가능',
        conflicts=[],
        papers_for_validation=papers_for_validation,
        regulations_for_validation=regulations_for_validation,
    )
