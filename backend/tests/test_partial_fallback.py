import pytest
from app.pipeline.orchestrator import run_verification
from app.schemas.api import VerificationRequest


@pytest.mark.asyncio
async def test_verification_survives_agent_failure(monkeypatch):
    async def raise_error(_claims):
        raise RuntimeError('forced scientific failure')

    monkeypatch.setattr('app.pipeline.orchestrator.run_scientific', raise_error)

    req = VerificationRequest(input_type='text', content='테스트 텍스트')
    result = await run_verification(req)

    assert result.scientific.error is not None
    assert result.report_markdown
