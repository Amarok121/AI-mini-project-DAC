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

`run_verification()`는 LangGraph 기반 그래프를 직접 실행합니다.
따라서 `requirements.txt`의 `langgraph`와 `langchain` 설치가 필수입니다.

## LangGraph Flow
1. `preprocess`
2. `extract_claims`
3. `validate_agents`
4. `cross_validate`
5. `report`

각 노드의 역할은 `backend/app/pipeline/verification_graph.py`에 주석으로 정리해두었습니다.

## LangChain Tools
- 뉴스 검색: `backend/app/tools/industrial.py`의 `search_naver_news`
- 특허 검색: `search_kipris_publication`
- 행정처리 이력: `search_kipris_prosecution`
- 인용문헌: `search_kipris_citations`

LangChain과 LangGraph가 필수입니다. 설치되지 않으면 실행하지 않습니다.

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
- API는 `LangGraph` 기반 `POST /verify` 결과 즉시 반환 방식입니다.
- 충돌 가능성이 높은 영역은 `backend/app/pipeline/verification_graph.py`와 각 agent 내부입니다.
- 팀 공통 상태 정의는 `backend/app/pipeline/state.py`에 둡니다.
