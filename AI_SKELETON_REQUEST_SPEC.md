# 자율적 리서치 AI Agent 스켈레톤 생성 요청서 (v1.3)

작성일: 2026-04-13
용도: AI 코딩 도구에 전달할 팀 공통 스켈레톤 명세 (단일 회사, 동기 API 기준)

## 핵심 원칙
- Report Generator는 Agent로 구현
- 한 회사 전제 (`company_context` 미사용)
- `POST /verify` 동기 처리로 즉시 결과 반환
- 외부 API는 TODO + Mock 우선

## 최소 디렉토리
- backend/app/main.py
- backend/app/api/routes.py
- backend/app/pipeline/orchestrator.py
- backend/app/agents/*
- backend/app/preprocessing/*
- backend/app/schemas/*
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
1. parse_input
2. clean_text
3. claim_extractor
4. scientific/industrial/regulatory 병렬 실행 (`asyncio.gather`)
5. cross_validation
6. report agent

## 실패 처리
- 특정 agent 실패 시 기본 출력으로 대체하고 전체 보고서는 생성
- 실패 정보는 해당 agent output의 `error` 필드에 기록

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
