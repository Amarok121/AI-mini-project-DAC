from app.schemas.claim import Claim
from app.schemas.agent_result import ScientificAgentOutput, PaperResult


async def run(claims: list[Claim]) -> ScientificAgentOutput:
    # TODO: semantic_scholar/arxiv/openalex 연동 + GRADE 점수 계산
    paper = PaperResult(
        title='Mock Paper on DAC',
        authors=['A. Researcher'],
        year=2024,
        journal='Energy Journal',
        url='https://example.org/paper',
        grade_score=0.72,
        grade_level='MED',
    )
    return ScientificAgentOutput(
        papers=[paper],
        overall_grade='MED',
        trl_estimate='TRL 5~6',
        summary='실험실-파일럿 사이 근거가 확인됨 (mock).',
    )
