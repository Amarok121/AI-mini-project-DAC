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
팀 명세(`IMPLEMENTATION_NOTES.md`)에서는 `backend/app/tools/` 아래에 LangChain Tool을 두는 것을 전제로 합니다. 현재 브랜치에는 해당 디렉터리가 없을 수 있으며, 산업 측 검색·특허 로직은 `backend/app/agents/industrial/`(`news_agent.py`, `patent_agent.py` 등)에서 다룹니다.

LangChain(`langchain-core` 등)과 LangGraph는 `requirements.txt`에 포함되어야 합니다.

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
- `POST /verify`는 `LangGraph` 그래프(`backend/app/pipeline/verification_graph.py`)로 실행되어 결과를 즉시 반환합니다. 공유 상태 스키마는 `backend/app/pipeline/state.py`입니다.
- Scientific / Industrial / Regulatory 에이전트 구현은 `backend/app/agents/` 하위이며, 파이프라인과 함께 자주 수정되는 영역입니다.
- 외부 API·키가 없으면 일부 에이전트는 Mock 또는 축약 동작을 할 수 있습니다.
