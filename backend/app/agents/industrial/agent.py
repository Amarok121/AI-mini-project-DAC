from app.schemas.claim import Claim
from app.schemas.agent_result import IndustrialAgentOutput
from .news_agent import run_news
from .patent_agent import run_patent


async def run(claims: list[Claim]) -> IndustrialAgentOutput:
    # TODO: 뉴스/특허 신호 결합 후 MRL 계산 로직 고도화
    news = await run_news(claims)
    patents = await run_patent(claims)
    return IndustrialAgentOutput(
        news=news,
        patents=patents,
        overall_level='MED',
        mrl_estimate='MRL 3~4',
        summary='산업 적용 신호는 있으나 양산 검증은 부족 (mock).',
    )
