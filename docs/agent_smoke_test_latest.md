# 에이전트 스모크 테스트 결과

- 실행 시각(UTC): 2026-04-14T01:53:08.088045+00:00
- 파이프라인: `run_verification` → LangGraph (`verification_graph.py`)

## 1. 생성된 보고서 (report_markdown)

# 기술 검증·도입 가능성 보고서: DAC 직접공기포집

## 1. Executive Summary
- **초점:** 기술도입 가능성·장기 경제성 관점 (TRL/MRL/CRI는 교차검증·향후 보강).
- 최종 판단: **조건부 가능**

## 2. Agent 요약
- Scientific: LOW (TRL 3~5) — GRADE 스켈레톤 가중평균(상위3): 0.3297
- Industrial: MED (MRL 3~4)
- Regulatory: 불명확 (LOW)

## 3. 도입 체크리스트 (초안)
- 파일럿 CAPEX/OPEX·회수기간(Payback) 가정 검증
- 규제·인센티브(예: IRA 45Q, 국내 탄소 정책) 법무 검토
- CCU·탄소 배출권·에너지 단가 시나리오(장기) 민감도
- 12개월 내 KPI 정의

## 4. 규제·정책 환경 (요약)

- 적용성 판정: **불명확** (신뢰도 지표: LOW — 규제 ‘출처 신뢰’가 아닌 **해석 불확실성** 표시)

- 참고 링크:
  - https://www.law.go.kr/lsInfoP.do?lsiSeq=204195
  - https://www.law.go.kr/lsInfoP.do?lsiSeq=281191&viewCls=lsRvsDocInfoR
  - https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=208137
  - https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=258079
  - https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=103950
  - https://law.go.kr/LSW/lsInfoP.do?lsiSeq=90215
  - https://www.law.go.kr/lsInfoP.do?lsiSeq=162062
  - https://www.law.go.kr/LSW/lsInfoP.do?lsId=009245
  - https://law.go.kr/LSW/lsInfoP.do?lsiSeq=140548&viewCls=lsRvsDocInfoR
  - https://law.go.kr/LSW/lsInfoP.do?lsiSeq=238751&viewCls=lsRvsDocInfoR

- **판단 근거 요약 (에이전트):**

주장에 대한 공식적인 검증 자료가 부족하여 확인할 수 없음.

- 법령·정책명 추출 후보 (2단계):
  - 미세먼지 저감 및 관리에 관한 특별법
  - 미세먼지 저감 및 관리에 관한 특별법 시행령
  - 대기환경보전법
  - 환경분야 시험ㆍ검사 등에 관한 법률
  - 범죄수익은닉의 규제 및 처벌 등에 관한 법률

- 파이프라인 메모:
  - [KR] '미세먼지 저감 및 관리에 관한 특별법': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '미세먼지 저감 및 관리에 관한 특별법 시행령': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '대기환경보전법': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '환경분야 시험ㆍ검사 등에 관한 법률': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '범죄수익은닉의 규제 및 처벌 등에 관한 법률': law.go.kr 결과 없음 또는 OC 키 미설정



## 2. Scientific 에이전트 요약

- **overall_grade:** LOW
- **trl_estimate:** TRL 3~5
- **search_sources:** ['semantic_scholar', 'openalex', 'arxiv']
- **논문 수:** 2
- **error:** (없음)
- **grade_breakdown.weighted_total:** 0.3297

### 툴·데이터 소스 동작 (Scientific)

1. **Semantic Scholar** — `graph/v1/paper/search` (선택 헤더 `x-api-key`).
2. **OpenAlex** — `works` 검색, User-Agent에 `OPENALEX_CONTACT_EMAIL` 권장.
3. **arXiv** — `export.arxiv.org/api/query` Atom 파싱, API 키 없음.
4. 결과는 제목 정규화로 병합 후 `grade_evaluator` 휴리스틱으로 점수화.

상위 논문 예시(최대 3건):
1. Observations of the Ultraviolet-Bright Star ZNG 1 in the Globular Cluster M5 (NGC 5904)… — citations=0, grade=LOW
2. Random Stimuli Generation for the Verification of Quantum Circuits… — citations=0, grade=LOW

## 3. Regulatory 에이전트 요약

- **verdict:** 불명확
- **confidence:** LOW
- **source_urls (개수):** 10
- **error:** (없음)
- **pipeline_notes:**
  - [KR] '미세먼지 저감 및 관리에 관한 특별법': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '미세먼지 저감 및 관리에 관한 특별법 시행령': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '대기환경보전법': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '환경분야 시험ㆍ검사 등에 관한 법률': law.go.kr 결과 없음 또는 OC 키 미설정
  - [KR] '범죄수익은닉의 규제 및 처벌 등에 관한 법률': law.go.kr 결과 없음 또는 OC 키 미설정

### 툴·데이터 소스 동작 (Regulatory)

1. **Tavily** — 규제·정책 도메인 검색 (`TAVILY_API_KEY`).
2. **LangChain** — 법령명 추출·적용성 해석에 `ChatOpenAI` + JSON (`law_extract.py`, `regulatory_llm.py`).
3. **국내 law.go.kr** — `LAW_GO_KR_API_KEY` 및 MST 있을 때 `lawService.do` 상세.
4. **EU** — 스니펫/이름에서 CELEX 추정 후 EUR-Lex HTML (`eurlex.py`), 실패 시 Tavily 스니펫.

## 4. Industrial / Cross-validation (참고)

- industrial.error: (없음)
- cross_validation.overall_verdict: 조건부 가능
