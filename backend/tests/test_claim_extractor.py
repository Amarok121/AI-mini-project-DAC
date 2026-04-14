"""클레임 추출: API 키 없을 때 폴백 및 구조 검증."""

import pytest

from app.core.config import settings
from app.agents.claim_extractor import _fallback_claims_from_text, run_claim_extractor


@pytest.mark.asyncio
async def test_fallback_claims_nonempty_text():
    claims = _fallback_claims_from_text("DAC 파일럿 1만 톤 규모 검토 중.")
    assert len(claims) == 1
    assert "DAC" in claims[0].claim or "파일럿" in claims[0].claim


@pytest.mark.asyncio
async def test_run_without_openai_key_uses_fallback(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    claims = await run_claim_extractor("탄소 포집 기술 도입을 검토한다.")
    assert len(claims) >= 1
    assert claims[0].technology


@pytest.mark.asyncio
async def test_empty_text_returns_empty_list(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    claims = await run_claim_extractor("   ")
    assert claims == []
