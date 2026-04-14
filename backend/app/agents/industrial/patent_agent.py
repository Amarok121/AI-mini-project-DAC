from app.schemas.claim import Claim
from app.schemas.agent_result import PatentResult


async def run_patent(claims: list[Claim]) -> list[PatentResult]:
    # TODO: KIPRIS 연동 + 핵심특허 판별
    return [
        PatentResult(
            title='DAC 흡착제 관련 특허',
            applicant='Mock Corp',
            application_date='2025-01-10',
            status='출원',
            is_core_tech=True,
            url='https://example.org/patent',
            summary='직접공기포집 장치·흡착제 조합을 다루는 mock 특허다.',
            key_point='DAC 장치 구성',
            core_level='MED',
            flags=['mock', '기술 연관성 예시'],
        )
    ]
