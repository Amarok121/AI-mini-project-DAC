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
