# Agent Responsibility and Evidence Pack

작성일: 2026-04-14  
목적: 각 에이전트가 무엇을 책임져야 하는지, 그리고 다음 단계로 어떤 구조화된 결과를 넘겨야 하는지 정리한 팀 공유 문서

## 1. 핵심 원칙

- 각 에이전트는 자기 도메인의 `검색 + 판단 + 근거 정리`까지 책임진다.
- `Report Agent`는 기본적으로 재검색하지 않고, 받은 evidence pack을 문장화한다.
- `Cross Validator`는 새로 탐색하기보다, 주어진 근거들 사이의 충돌/과장/조건 누락을 판정한다.
- 벡터DB는 보조 저장/검색 수단일 수 있지만, 최종 판정의 주 근거는 구조화된 evidence pack이다.

## 2. 책임 경계

### 2.1 Scientific Agent

책임:

- 논문 검색
- 논문 요약
- 실험 조건 / 한계 / 적용 범위 추출
- GRADE 평가

출력의 핵심:

- `papers`
- `overall_grade`
- `summary`
- `error`

### 2.2 Industrial Agent

책임:

- 뉴스 검색
- 특허 검색
- 각 소스의 신뢰도 / 핵심성 판단
- 산업 신호 요약
- MRL 추정

출력의 핵심:

- `news`
- `patents`
- `overall_level`
- `mrl_estimate`
- `summary`
- `error`

### 2.3 Regulatory Agent

책임:

- 규제/인센티브 탐색
- 적용 가능성 판단
- 리스크 정리

출력의 핵심:

- `verdict`
- `confidence`
- `applicable_regulations`
- `incentives`
- `risks`
- `requires_expert_review`
- `source_urls`
- `error`

### 2.4 Cross Validator

책임:

- 클레임과 evidence pack을 비교
- 뉴스 vs 논문 간 과장 여부 / 조건 누락 / 근거 부족 판정
- 논문과 뉴스의 표현 수준 차이 탐지
- 규제 리스크가 있으면 플래그 부여

원칙:

- 기본적으로 재검색하지 않는다.
- 주어진 evidence를 기준으로 판정한다.
- 필요할 때만 보조 검색을 별도 단계로 분리한다.

### 2.5 Report Agent

책임:

- 구조화된 evidence pack을 읽고 마크다운 보고서 생성
- 사람이 읽기 쉬운 문장으로 요약
- 최종 판단과 근거를 섹션별로 정리

원칙:

- 기본적으로 재검색하지 않는다.
- 받은 데이터를 문장화하는 데 집중한다.
- 부족한 근거가 있으면 “근거 부족”으로 명시한다.

## 3. Evidence Pack 정의

Evidence pack은 원문 전체가 아니라, 판정과 보고서 작성에 필요한 최소 충분 근거 묶음이다.

구성 요소:

- 클레임 원문
- 소스별 요약
- 핵심 문장 / excerpt
- 조건 / 한계
- 신뢰도 점수
- flags
- source url
- 날짜 / 출처 / 상태 메타데이터

### 3.1 뉴스 evidence

```json
{
  "title": "공기서 포집한 CO2로 맥주 만든다",
  "publisher": "chosun.com",
  "published_at": "2026-04-13",
  "url": "https://...",
  "craap_score": 0.63,
  "craap_level": "MED",
  "summary": "기업 발표를 바탕으로 DAC 기술의 실증 확대를 다룬 기사다.",
  "excerpt": "상용화 직전 수준이라고 밝혔다.",
  "flags": [
    "기업 발표 기반",
    "독립 취재 약함"
  ]
}
```

### 3.2 논문 evidence

```json
{
  "title": "DAC 흡착 성능 평가",
  "authors": ["A. Researcher"],
  "year": 2024,
  "url": "https://...",
  "grade_score": 0.72,
  "grade_level": "MED",
  "summary": "이 논문은 DAC 흡착제의 성능을 실험실 조건에서 검증한 연구다. 25도와 건조 환경에서 높은 포집 효율을 보였지만, 실환경이나 파일럿 규모 검증은 포함되지 않았다. 따라서 기술 가능성은 보여주지만 상용 환경 일반화에는 제한이 있다.",
  "key_point": "lab-scale에서 성능 검증",
  "excerpt": "25도, 건조 조건에서만 우수한 결과를 보였다.",
  "conditions": [
    "lab-scale",
    "25도",
    "건조 환경"
  ],
  "limitations": [
    "실환경 미검증",
    "파일럿 규모 아님"
  ],
  "reason": "실험 조건이 제한적이어서 뉴스가 상용화 가능성처럼 서술할 경우 과장일 수 있다."
}
```

### 3.3 특허 evidence

```json
{
  "title": "건식 이산화탄소 흡수제를 이용한 직접공기포집 장치",
  "applicant": "(주)로우카본",
  "application_date": "2025-03-24",
  "status": "등록",
  "summary": "이 특허는 직접공기포집 장치의 구조와 흡착제 조합을 다루는 등록 특허다. DAC 관련 장치 구성이 명시되어 있으며, 기술의 존재성과 사업화 방향성을 확인하는 데 유용하다. 다만 핵심기술인지 여부는 인용관계와 청구항 범위를 함께 봐야 한다.",
  "key_point": "DAC 장치 구조를 다룸",
  "core_level": "MED",
  "flags": [
    "등록 특허",
    "기술 연관성 높음"
  ],
  "url": "https://..."
}
```

## 4. 검증 입력 구조

Cross Validator에 주는 입력은 다음처럼 구성하는 것이 좋다.

```json
{
  "claims": [
    {
      "technology": "DAC 직접공기포집",
      "claim": "1,000시간 연속 운전 성공",
      "application": "탄소 저감",
      "type": "성능 지표",
      "status": "달성"
    }
  ],
  "scientific": {
    "overall_grade": "MED",
    "papers": [
      {
        "title": "...",
        "summary": "...",
        "excerpt": "...",
        "conditions": ["..."],
        "limitations": ["..."],
        "grade_score": 0.72,
        "grade_level": "MED",
        "url": "..."
      }
    ]
  },
  "industrial": {
    "overall_level": "MED",
    "mrl_estimate": "MRL 5~6",
    "news": [
      {
        "title": "...",
        "summary": "...",
        "excerpt": "...",
        "craap_score": 0.63,
        "craap_level": "MED",
        "flags": ["..."],
        "url": "..."
      }
    ],
    "patents": [
      {
        "title": "...",
        "summary": "...",
        "status": "등록",
        "core_level": "MED",
        "flags": ["..."],
        "url": "..."
      }
    ]
  },
  "regulatory": {
    "verdict": "불명확",
    "confidence": "MED",
    "risks": ["..."],
    "source_urls": ["..."]
  }
}
```

## 5. Report Agent 입력 원칙

Report Agent에는 원문 전체가 아니라, 다음을 우선 전달한다.

- 클레임 목록
- 소스별 요약
- 핵심 excerpts
- 조건 / 한계
- flags
- 최종 판정

벡터DB를 사용하더라도, 보고서 에이전트의 주 입력은 구조화된 JSON evidence pack이어야 한다.  
논문 evidence는 특히 서술형 요약이 더 길어야 하며, 연구 목적/조건/결과/한계를 포함하는 3~6문장 수준이 적절하다.

## 6. 검색어와 결과 책임

- 검색어 생성은 에이전트 내부의 보조 함수가 담당한다.
- 검색어는 최종 결과물이 아니라 retrieval helper이다.
- 최종 결과물은 항상 구조화된 evidence pack이어야 한다.

## 7. 권장 실행 순서

1. 수집 에이전트가 후보 문서를 탐색한다.
2. 문서에서 핵심 문장과 메타데이터를 추출한다.
3. evidence pack을 만든다.
4. Cross Validator가 그 evidence pack을 보고 판정한다.
5. Report Agent가 그 결과를 사람 읽기 좋은 보고서로 쓴다.

## 8. 실무 메모

- `Report Agent`가 다시 처음부터 검색하는 구조는 기본값으로 두지 않는다.
- `Cross Validator`가 다시 처음부터 검색하는 구조도 기본값으로 두지 않는다.
- “누가 무엇을 책임지는가”를 분리해야 디버깅과 협업이 쉬워진다.
- 뉴스/논문/특허/규제 모두 최종적으로는 `구조화된 결과 + 짧은 근거문 + 메타데이터`가 중요하다.
