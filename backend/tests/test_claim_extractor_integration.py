"""OPENAI_API_KEY가 있을 때만 실행되는 클레임 추출 스모크 (비용·네트워크 발생)."""

import pytest

from app.core.config import settings
from app.agents.claim_extractor import run_claim_extractor


@pytest.mark.asyncio
async def test_openai_extracts_structured_claims_from_dac_text():
    if not (settings.OPENAI_API_KEY or "").strip():
        pytest.skip("OPENAI_API_KEY not set — set in .env to run integration test")

    text = """
    회사 A는 2026년까지 DAC(직접공기포집) 시범 설비로 연간 5천 톤 CO2를 포집하는 것을 목표로 한다.
    2025년 1분기에는 소규모 프로토타입에서 500시간 연속 운전을 달성했다고 밝혔다.
    EU CBAM과 국내 탄소중립기본법 준수 여부는 법무팀이 검토 중이다.
    """
    claims = await run_claim_extractor(text)

    assert len(claims) >= 1
    for c in claims:
        assert len(c.claim) >= 8
        assert c.technology
        assert c.status in ("달성", "목표")
        assert c.type in (
            "성능 지표",
            "경제성",
            "규제",
            "안전성",
            "일반",
            "환경",
            "사업성",
            "기술성",
            "일정",
            "규모",
        )
