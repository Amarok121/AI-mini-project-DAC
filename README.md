# AI-mini-project-DAC

FastAPI + Vue + Chroma 기반 **기술 주장 검증·도입 가능성 조사** 스켈레톤입니다.

프로젝트 초점은 단순 팩트 체크를 넘어, **CCU·탄소/에너지 전환 기술 도입이 장기적으로 회사에 이득이 될지(경제성·규제·성숙도)**를 보는 데 맞춥니다. 예: DAC 도입, IRA 45Q·국내 탄소 정책과의 정합성 등. 사내 DB 대신 **DART 사업보고서(로컬)** 로 회사 맥락을 가정합니다.

상세 정렬 메모: [`docs/PROJECT_FOCUS.md`](docs/PROJECT_FOCUS.md)

## Environment setup
```bash
cp .env.example .env
```

`DART_DOCS_DIR` 아래에 회사별 폴더를 두고 문서를 넣어 사용합니다.
예:
- `data/dart/SK이노베이션/2024_report.pdf`
- `data/dart/SK이노베이션/subdir/appendix.pdf`

PDF는 재귀 탐색되므로 `data/dart/{회사명}/문서.pdf` 구조를 그대로 사용해도 됩니다.

### Demo PDFs
현재 데모용으로는 `data/dart/SK_innovaion/` 아래 PDF 4개를 사용합니다.

- `[SK이노베이션]사업보고서(2026.03.16)_사업의 내용.pdf`
  - 회사의 사업 구조, 주요 제품/기술, 생산 및 투자 방향을 파악하기 위한 핵심 사업 개요 자료
- `제19기 영업보고서.pdf`
  - 최근 경영 현황, 주요 사업 성과, 운영 흐름을 빠르게 확인하기 위한 요약형 공시 자료
- `SK On Green Financing Framework 2025.pdf`
  - 배터리/친환경 투자, 지속가능금융, 녹색 프로젝트 기준 등 ESG·전환 투자 맥락을 보강하는 자료
- `SKI_제19기 결산공고.pdf`
  - 재무 상태와 손익 흐름을 확인해 기술 도입의 사업성/투자 여력을 보조적으로 판단하기 위한 자료

이 파일들은 데모에서 SK이노베이션의 사업 맥락을 RAG로 보강하기 위한 용도이며,
기술 주장 자체의 과학적 진위를 직접 증명하는 자료라기보다는
`회사 현황 / 설비 / 투자 / 재무 / 사업 포트폴리오` 문맥을 제공하는 역할에 가깝습니다.

## Run backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

`run_verification()`는 LangGraph 기반 그래프를 직접 실행합니다.
따라서 `requirements.txt`의 `langgraph`와 `langchain` 설치가 필수입니다.

## Send a query (Terminal 2)
백엔드 서버(`uvicorn ... --reload --port 8000`)를 한 터미널에서 실행한 상태에서, 다른 터미널에서 아래처럼 `POST /verify`를 호출하면 됩니다.

```bash
curl -sS -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"input_type":"text","content":"공기 중 CO2를 직접 포집하는 DAC 기술을 1,000시간 연속 운전했다고 하는데 도입 가능성은?"}'
```

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
docker compose up --build
```

## First-time Docker setup
현재 프로젝트는 별도 `chroma` 컨테이너 대신 로컬 저장형 Chroma(`PersistentClient`)를 사용합니다.
벡터 데이터는 호스트의 `data/chroma/` 디렉토리에 저장되며, backend/ingest 컨테이너가 이를 공유합니다.

처음 실행은 아래 순서를 권장합니다.

1. 기본 서비스 기동
```bash
docker compose up --build
```

2. 회사 문서 1회 적재
```bash
docker compose --profile ingest run --rm ingest
```

3. 헬스체크 확인
```bash
curl http://localhost:8000/health
```

정상 응답:
```json
{"status":"ok"}
```

## Chroma storage
- Chroma 벡터 데이터는 `data/chroma/`에 저장됩니다.
- 같은 머신에서는 이 디렉토리가 유지되는 한 모델/벡터 데이터를 계속 재사용할 수 있습니다.
- HuggingFace 모델 캐시는 `./.cache/huggingface`에 저장되며, backend와 ingest가 함께 사용합니다.

### Chroma files overview
`data/chroma/` 아래에는 Chroma 로컬 DB가 여러 파일로 나뉘어 저장됩니다.

- `chroma.sqlite3`: 컬렉션/메타데이터/문서 인덱스 정보를 담는 SQLite 파일
- `data_level0.bin`: 벡터 인덱스의 실제 데이터가 저장되는 바이너리 파일
- `length.bin`: 인덱스 길이 및 엔트리 크기 관련 메타 정보를 담는 파일
- `header.bin`, `link_lists.bin`: HNSW 기반 검색 인덱스의 헤더/링크 구조를 저장하는 파일

참고:
- `backend/data/`는 팀 공용 DB 기준 경로가 아니라 로컬 실행 중 생길 수 있는 보조/legacy 산출물 경로입니다.
- 팀원이 함께 재사용해야 하는 Chroma 데이터는 루트의 `data/chroma/` 기준으로 보면 됩니다.

## When to run ingest again
아래 경우에만 `docker compose --profile ingest run --rm ingest`를 다시 실행하면 됩니다.
- `data/dart/` 아래에 새 PDF를 추가했을 때
- `data/chroma/`를 삭제했을 때
- 청킹/임베딩 로직이 바뀌어서 기존 벡터 데이터를 새 기준으로 다시 만들고 싶을 때

이미 적재된 상태라면 ingest를 다시 돌릴 필요는 없습니다.
현재 ingest는 기존 메타데이터를 보고 이미 적재된 PDF를 파싱 없이 skip합니다.

## Notes
- `POST /verify`는 `LangGraph` 그래프(`backend/app/pipeline/verification_graph.py`)로 실행되어 결과를 즉시 반환합니다. 공유 상태 스키마는 `backend/app/pipeline/state.py`입니다.
- Scientific / Industrial / Regulatory 에이전트 구현은 `backend/app/agents/` 하위이며, 파이프라인과 함께 자주 수정되는 영역입니다.
- 외부 API·키가 없으면 일부 에이전트는 Mock 또는 축약 동작을 할 수 있습니다.
- 기본 기동 서비스는 `backend`, `frontend`이고, `ingest`는 수동 1회 적재용 프로필 서비스입니다.
- 문서 적재 결과는 `data/chroma/` 로컬 디렉토리에 저장됩니다.
- 팀원이 `git pull`만 받는 경우 벡터 데이터는 자동 공유되지 않으므로, 각자 `data/chroma/`를 보유하지 않았다면 한 번은 ingest를 실행해야 합니다.
- 동일 문서로 ingest를 다시 실행해도 청크 id 기준으로 중복 적재는 skip됩니다.
