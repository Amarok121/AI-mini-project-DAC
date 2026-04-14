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
            summary='기업 발표를 바탕으로 DAC 파일럿 확대 소식을 다룬 mock 기사다.',
            excerpt='상용화에 근접했다는 표현이 포함될 수 있다.',
            flags=['기업 발표 기반', 'mock'],
        )
    ]
