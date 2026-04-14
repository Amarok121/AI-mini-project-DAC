# AI-mini-project-DAC

FastAPI + Vue + Chroma 기반 **기술 주장 검증·도입 가능성 조사** 스켈레톤입니다.

프로젝트 초점은 단순 팩트 체크를 넘어, **CCU·탄소/에너지 전환 기술 도입이 장기적으로 회사에 이득이 될지(경제성·규제·성숙도)**를 보는 데 맞춥니다. 예: DAC 도입, IRA 45Q·국내 탄소 정책과의 정합성 등. 사내 DB 대신 **DART 사업보고서(로컬)** 로 회사 맥락을 가정합니다.

상세 정렬 메모: [`docs/PROJECT_FOCUS.md`](docs/PROJECT_FOCUS.md)

## Environment setup
```bash
cp .env.example .env
```

`DART_DOCS_DIR` 아래에 회사 문서를 넣고 사용합니다.
예: `data/dart/default/2024_report.pdf`

## Run backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run tests
```bash
cd backend
pytest -q
```

## Run docker compose
```bash
docker-compose up --build
```

## Notes
- 현재 외부 API 연동은 TODO + Mock 출력입니다.
- API는 단순화되어 `POST /verify` 결과 즉시 반환 방식입니다.
- 규제 에이전트: **Tavily** 탐색은 구현됨 → 정부 포털 원문 fetch·LLM 적용성 해석은 TODO (`backend/app/agents/regulatory/`).
