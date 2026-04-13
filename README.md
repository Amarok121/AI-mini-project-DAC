# AI-mini-project-DAC

Synchronous skeleton for competitor tech-claim verification (FastAPI + Vue + Chroma).

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
