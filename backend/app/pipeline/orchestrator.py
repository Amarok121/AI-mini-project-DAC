import asyncio
from app.schemas.api import VerificationRequest, VerificationResponse
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
)
from app.preprocessing.input_parser import parse_input
from app.preprocessing.text_cleaner import clean_text
from app.agents.claim_extractor import run_claim_extractor
from app.agents.scientific.agent import run as run_scientific
from app.agents.industrial.agent import run as run_industrial
from app.agents.regulatory.agent import run as run_regulatory
from app.agents.cross_validation.agent import run as run_cross_validation
from app.agents.report.agent import run as run_report


async def run_verification(request: VerificationRequest) -> VerificationResponse:
    """
    동기형 검증 파이프라인.
    - 요청 1건을 즉시 처리해 최종 응답을 반환
    - 개별 에이전트 실패는 기본값으로 대체해 전체 리포트는 생성
    """
    raw_text = await parse_input(request.input_type, request.content)
    clean = clean_text(raw_text)
    claims = await run_claim_extractor(clean)

    scientific, industrial, regulatory = await asyncio.gather(
        run_scientific(claims),
        run_industrial(claims),
        run_regulatory(claims),
        return_exceptions=True,
    )

    if isinstance(scientific, Exception):
        scientific = ScientificAgentOutput(error=str(scientific), summary='Scientific agent failed.')
    if isinstance(industrial, Exception):
        industrial = IndustrialAgentOutput(error=str(industrial), summary='Industrial agent failed.')
    if isinstance(regulatory, Exception):
        regulatory = RegulatoryAgentOutput(error=str(regulatory))

    cross = await run_cross_validation(claims, scientific, industrial, regulatory)
    report_markdown = await run_report(claims, scientific, industrial, regulatory, cross)

    return VerificationResponse(
        report_markdown=report_markdown,
        claims=claims,
        scientific=scientific,
        industrial=industrial,
        regulatory=regulatory,
        cross_validation=cross,
    )
