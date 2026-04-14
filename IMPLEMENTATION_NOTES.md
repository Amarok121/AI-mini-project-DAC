# 자율적 리서치 AI Agent 구현 참고사항 (v1.3)

작성일: 2026-04-13
용도: AI 코딩 도구에 전달할 팀 공통 스켈레톤 명세 (단일 회사, LangGraph 기반 동기 API 기준)

## 핵심 원칙
- Report Generator는 Agent로 구현
- 한 회사 전제 (`company_context` 미사용)
- `POST /verify` 동기 처리로 즉시 결과 반환
- 외부 API는 TODO + Mock 우선
- 파이프라인 실행은 LangGraph를 사용한다
- LLM 호출/외부 API 래핑은 LangChain Tool로 표준화한다
- LangChain/LangGraph는 필수 의존성으로 두고, 호환 레이어는 두지 않는다

## 최소 디렉토리
- backend/app/main.py
- backend/app/api/routes.py
- backend/app/pipeline/orchestrator.py
- backend/app/pipeline/verification_graph.py
- backend/app/pipeline/state.py
- backend/app/agents/*
- backend/app/preprocessing/*
- backend/app/schemas/*
- backend/app/tools/*
- backend/app/services/{dart.py,vector_store.py,rag_retriever.py}

## API 계약
- `POST /verify` -> `VerificationResponse`
- `GET /health` -> `{status: "ok"}`

## 요청/응답
- VerificationRequest
  - input_type: `url | text | title`
  - content: string
- VerificationResponse
  - report_markdown
  - claims
  - scientific
  - industrial
  - regulatory
  - cross_validation

## 파이프라인
1. `preprocess`
2. `extract_claims`
3. `validate_agents`
4. `cross_validate`
5. `report`

### LangGraph 노드 역할
- `preprocess`: 입력을 본문 텍스트로 변환하고 정제
- `extract_claims`: 검증 가능한 기술 클레임 구조화
- `validate_agents`: scientific / industrial / regulatory 병렬 실행
- `cross_validate`: 에이전트 결과 통합 및 충돌 탐지
- `report`: 최종 보고서 생성 및 응답 객체 반환

## LangChain Tool 구조
- `app/tools/industrial.py`
  - `search_naver_news`
  - `search_kipris_publication`
  - `search_kipris_prosecution`
  - `search_kipris_citations`
- 각 Tool은 LangChain Tool 객체로 동작한다
- agent는 Tool을 직접 호출해서 결과를 사용한다
- scientific/regulatory/report 쪽도 같은 규칙으로 Tool/Prompt를 LangChain 기반으로 붙인다

## 실패 처리
- 특정 agent 실패 시 기본 출력으로 대체하고 전체 보고서는 생성
- 실패 정보는 해당 agent output의 `error` 필드에 기록
- LangGraph 노드 추가 시 기존 노드와 충돌하지 않도록 `verification_graph.py`에만 흐름을 집중시킨다
- Graph state는 `pipeline/state.py`에서 일원화한다

## DART 문서 소스
- API 호출 대신 로컬 PDF 사용
- 경로: `DART_DOCS_DIR` (기본 `./data/dart`)
- 예시: `data/dart/default/2024_report.pdf`
- `dart.py`에서 PDF 텍스트 추출 TODO 유지

## 테스트 최소 2종
- `/verify` 즉시 응답 테스트
- agent 실패 fallback 테스트

## 환경설정
```bash
cp .env.example .env
```

## 팀 공유 메모
- 변경 충돌이 가장 날 가능성이 큰 파일은 `backend/app/pipeline/verification_graph.py`
- 각 agent는 독립적으로 수정 가능하지만, 상태 이름과 반환 스키마는 `schemas/` 기준으로 맞춘다
- 노드 추가나 분기 변경은 팀 공유 후 반영한다
- Tool 추가 시 `app/tools/` 아래에 먼저 정의하고 agent에서 재사용한다
- 개발 환경에는 `langchain`과 `langgraph` 설치가 선행되어야 한다

---

## 팀 변경 기록 (자유 양식 — 각자 날짜·브랜치별로 아래에 추가)

### 2026-04-14 — `scientific-and-regulations` (Scientific / Regulatory 에이전트·병합)

**요약:** Scientific은 Semantic Scholar + OpenAlex + arXiv 검색을 제목 정규화로 병합한 뒤 GRADE 스타일 휴리스틱으로 점수화한다. Regulatory는 Tavily → (LangChain JSON) 법령명 추출 → law.go.kr·EUR-Lex 보조 fetch → (LangChain JSON) 적용성 해석 순으로 동작한다. LLM 호출은 `langchain_setup.get_chat_model`과 `ChatPromptTemplate` + `JsonOutputParser`를 사용한다. 파이프라인 진입은 `origin/main` 병합 후 **`orchestrator` → LangGraph `build_verification_graph()`** 가 표준이며, 예전 단일 `asyncio.gather` 구현은 대체되었다.

**추가·수정된 주요 경로**
| 영역 | 파일 |
|------|------|
| Scientific LCEL | `backend/app/agents/scientific/lc_chain.py`, `agent.py` |
| 검색 클라이언트 | `semantic_scholar.py`, `openalex.py`, `arxiv.py` |
| GRADE 스켈레톤 | `grade_evaluator.py` |
| 스키마 | `backend/app/schemas/agent_result.py` (`PaperResult`, `GradeDimensionScores`, …) |
| Regulatory LLM | `law_extract.py`, `regulatory_llm.py` |
| 포털·EU | `portal_fetch.py`, `eurlex.py` |
| 공통 LC | `backend/app/agents/langchain_setup.py` |
| 그래프 | `backend/app/pipeline/verification_graph.py`, `state.py`, `orchestrator.py` |
| 의존성 | `backend/requirements.txt` — `langchain-core`, `langchain-openai`, `langgraph`, 기존 API 클라이언트 |

**스모크 테스트 (로컬)**
- 스크립트: `backend/scripts/smoke_verify_report.py` — `run_verification` 1회 실행 후 요약 마크다운을 출력하거나 파일로 저장.
- 최근 실행 결과 예시: `docs/agent_smoke_test_latest.md` (저장소에 커밋해 두면 팀이 동일 절차로 재현 가능).
- 명령: `cd backend && PYTHONPATH=. python scripts/smoke_verify_report.py ../docs/agent_smoke_test_latest.md`

**이번 점검에서 수정한 버그 (참고)**
- `lc_chain`에서 `asyncio.to_thread(search_papers, q, 10)` 형태는 키워드 전용 인자(`limit`, `per_page`)와 맞지 않아 실패함 → `lambda: search_papers(q, limit=10)` 등으로 호출 수정.
- `law_extract` 시스템 프롬프트에 JSON 예시 `{"laws": …}`가 그대로 들어가 LangChain이 변수 `laws`로 해석함 → `{{"laws": …}}` 이스케이프.

**입·출력 계약 (요약)**
- API 전체: `VerificationRequest` / `VerificationResponse` (`schemas/api.py`).
- Scientific: `ScientificAgentOutput` — `papers`, `overall_grade`, `trl_estimate`, `grade_breakdown`, `search_sources`, `error` 등.
- Regulatory: `RegulatoryAgentOutput` — `verdict`, `confidence`, `applicable_regulations`, `source_urls`, `pipeline_notes`, `extracted_law_candidates`, `error` 등.
- 자연어 “프롬프트”로 입출력 전체가 정의된 것은 아니며, **규제 LLM 두 단계**(`law_extract`, `regulatory_llm`)에 시스템/유저 메시지가 명시되어 있다.

### 2026-04-14 (추가) — Claim extractor·보고서 출처

- **`claim_extractor`**: LangChain `ChatPromptTemplate` + OpenAI JSON으로 본문에서 최대 10개 `Claim` 추출. `OPENAI_API_KEY`가 없으면 본문 앞부분을 요약한 **폴백 클레임 1건**으로 파이프라인 유지.
- **`report`**: 마크다운에 **§3 근거·출처** — Scientific 상위 논문별 링크·DOI·arXiv·OpenAlex·S2 ID, Industrial 뉴스 링크. 규제 섹션은 **§5**로 번호 조정(기존 §4 참고 링크 유지).

**알려진 한계 / 후속**
- 클레임 품질은 입력 길이·LLM에 의존; 후속으로 스키마 검증·후처리·Few-shot을 강화할 수 있음.
- `backend/app/tools/` 디렉터리는 팀 명세상 계획이며, Industrial은 현재 `agents/industrial/`에서 동작.
- 논문/규제 검색 **부족 시 재시도 루프**는 미구현 — 레이트 리밋·비용 고려해 상한·백오프와 함께 도입 검토.
