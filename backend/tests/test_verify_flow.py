from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_verify_returns_result_immediately():
    payload = {'input_type': 'text', 'content': 'DAC 기술 기사 테스트'}
    resp = client.post('/verify', json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert 'report_markdown' in body
    assert 'cross_validation' in body
    assert isinstance(body['claims'], list)
    assert '근거·출처' in body['report_markdown']
