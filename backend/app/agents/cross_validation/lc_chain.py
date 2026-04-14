"""CrossValidator 에이전트 핵심 로직 (Chain)"""

import json
from typing import Any, Dict
from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
    ClaimVerificationResult,
    PerformanceGapResult,
)
from .confidence_scorer import combine_credibility
from .evaluator import (
    analyze_regulatory_conflict,
    analyze_performance_gaps
)

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class CrossValidatorChain:
    """Evidence Pack을 대조하여 Claim의 진위 여부를 판별하는 체인 클래스"""

    async def ainvoke(self, input_data: Dict[str, Any]) -> CrossValidatorOutput:
        claims: list[Claim] = input_data["claims"]
        scientific: ScientificAgentOutput = input_data["scientific"]
        industrial: IndustrialAgentOutput = input_data["industrial"]
        regulatory: RegulatoryAgentOutput = input_data["regulatory"]

        results: list[ClaimVerificationResult] = []
        conflicts: list[str] = []
        fake_claims: list[Claim] = []

        # [Step 1] 정적 분석 (Rules-based)
        performance_gaps = analyze_performance_gaps(scientific, industrial)
        regulatory_conflicts = analyze_regulatory_conflict(scientific, industrial, regulatory)

        # [Step 2] Evidence Pack 통합 문맥 생성 (LLM용)
        evidence_pack_context = "### Scientific Evidence (Papers)\n"
        for p in scientific.papers:
            evidence_pack_context += f"- Title: {p.title}\n  Summary: {p.summary}\n  Excerpt: {p.excerpt}\n  Conditions: {p.conditions}\n  Limitations: {p.limitations}\n"

        evidence_pack_context += "\n### Industrial Evidence (News & Patents)\n"
        for n in industrial.news:
            evidence_pack_context += f"- News: {n.title}\n  Summary: {n.summary}\n  Excerpt: {n.excerpt}\n  Flags: {n.flags}\n"

        # [Step 3] LLM을 통한 정밀 대조 (LLM-based)
        claims_dict = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in claims]

        prompt = f"""
        당신은 아첨 없는 냉철한 기술 감사관입니다. 
        제시된 'Evidence Pack'을 바탕으로 클레임의 진위 여부와 수치 왜곡을 판정하십시오.

        [사용자 클레임]
        {json.dumps(claims_dict, ensure_ascii=False)}

        [Evidence Pack]
        {evidence_pack_context}

        [분석 가이드라인]
        1. 지표 매핑: 뉴스의 주장 수치와 논문의 실증 데이터 중 '동일한 물리량'을 의미하는 것을 정확히 매핑하십시오.
        2. 수치 격차 판정 기준: 2.0x 이상 격차 시 CRITICAL_MISREPRESENTATION (허구 의심)
        3. 조건 누락: 논문의 'limitations'가 뉴스에서 무시되었는지 확인하십시오.

        결과는 "performance_gaps" 키를 가진 JSON 리스트로만 응답하십시오. (PerformanceGapResult 구조 준수)
        """

        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 기술적 모순을 잡아내는 데 특화된 감사관입니다. 절대 아첨하지 마십시오."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            for pg_data in data.get("performance_gaps", []):
                gap = PerformanceGapResult(**pg_data)
                performance_gaps.append(gap)
                if gap.status == 'CRITICAL_MISREPRESENTATION':
                    conflicts.append(f"[HYPE_ALERT] {gap.metric}: 이론적 근거({gap.sci_val}) 대비 {gap.hype_index}배 과장 감지.")
        except Exception as e:
            conflicts.append(f"[ANALYSIS_ERR] 교차 분석 실패: {str(e)}")

        # [Step 4] 최종 게이트키핑
        critical_hype = any(g.status == 'CRITICAL_MISREPRESENTATION' for g in performance_gaps)
        high_reg_risk = any(rc.severity == 'HIGH' for rc in regulatory_conflicts)

        for claim in claims:
            is_fake = critical_hype or (high_reg_risk and (scientific.overall_grade == 'LOW' or industrial.overall_level == 'LOW'))

            if is_fake:
                fake_claims.append(claim)
                verdict, credibility = '검증 실패 (허구/왜곡 의심)', 'LOW'
            else:
                credibility = combine_credibility(scientific.overall_grade, industrial.overall_level)
                verdict = '조건부 가능' if (scientific.overall_grade != 'LOW' and industrial.overall_level != 'LOW') else '판단 보류 (근거 부족)'

            results.append(
                ClaimVerificationResult(
                    claim=claim, 
                    credibility=credibility, 
                    verdict=verdict,
                    flags=['HYPE_DETECTED'] if critical_hype else (['REGULATORY_RISK'] if high_reg_risk else []),
                    mrl=industrial.mrl_estimate,
                    cri="" # CRI 추정은 Spec에서 제외됨
                )
            )

        return CrossValidatorOutput(
            results=results, 
            overall_verdict='주의 요망' if fake_claims or critical_hype or high_reg_risk else '조건부 가능', 
            conflicts=conflicts,
            performance_gaps=performance_gaps,
            regulatory_conflicts=regulatory_conflicts,
            fake_claims_detected=fake_claims
        )

cross_validator_chain = CrossValidatorChain()
