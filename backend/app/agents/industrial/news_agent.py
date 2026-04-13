from app.schemas.claim import Claim
from app.schemas.agent_result import NewsResult


async def run_news(claims: list[Claim]) -> list[NewsResult]:
    # TODO: 빅카인즈 연동 + CRAAP 평가
    return [
        NewsResult(
            title='DAC 실증 관련 보도',
            provider='Mock News',
            published_at='2026-04-13',
            url='https://example.org/news',
            craap_score=0.66,
            craap_level='MED',
        )
    ]
