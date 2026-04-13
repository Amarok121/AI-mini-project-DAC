from app.schemas.claim import Claim


async def run_claim_extractor(text: str) -> list[Claim]:
    # TODO: LLM JSON schema 강제 응답으로 교체
    # 스켈레톤: 예시 클레임 1건
    return [
        Claim(
            technology='DAC 직접공기포집',
            claim='1,000시간 연속 운전 성공',
            application='탄소 저감',
            type='성능 지표',
            status='달성',
        )
    ]
