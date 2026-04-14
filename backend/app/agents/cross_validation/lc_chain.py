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
        제시된 'Evidence Pack'을 바탕으로 클레임의 진위 여부와 서술적/수치적 왜곡을 판정하십시오.

        [사용자 클레임]
        {json.dumps(claims_dict, ensure_ascii=False)}

        [Evidence Pack]
        {evidence_pack_context}

        [분석 가이드라인]
        1. 수치 대조: 뉴스의 주장 수치와 논문의 실증 데이터 중 '동일한 물리량'을 매핑하십시오. 2.0x 이상 격차 시 판정하십시오.
        2. 서술 및 논리 대조 (중요):
           - 논문은 '이론적 모델/실험실 수준'인데 뉴스는 '실증 성공/상용화'로 묘사하는지 확인하십시오.
           - 논문의 '한계점(limitations)'이나 '특수 조건'이 뉴스에서 의도적으로 생략되었는지 확인하십시오.
           - 논문에서 입증되지 않은 효과를 뉴스가 논문의 권위를 빌려 과장하는지 확인하십시오.

        결과는 아래 형식을 가진 JSON 오브젝트로 응답하십시오. (PerformanceGapResult 필드명을 정확히 지키십시오)
        {{
            "performance_gaps": [
                {{
                    "metric": "수치 명칭 (예: 포집 비용)",
                    "sci_val": 0.0, // 논문 수치 (숫자만)
                    "ind_val": 0.0, // 뉴스 수치 (숫자만)
                    "hype_index": 0.0, // ind_val / sci_val (또는 그 반대, 격차 비율)
                    "status": "CRITICAL_MISREPRESENTATION | Hype Warning | Normal",
                    "description": "격차에 대한 설명",
                    "analyst_note": "감사관의 기술적 의견"
                }}
            ],
            "narrative_conflicts": [] // 서술적 모순/왜곡에 대한 구체적인 판단 근거 (문자열 리스트)
        }}
        """

        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 기술적 모순과 서술적 왜곡을 잡아내는 데 특화된 감사관입니다. 절대 아첨하지 마십시오."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            
            # 1. 수치적 격차 처리
            for pg_data in data.get("performance_gaps", []):
                gap = PerformanceGapResult(**pg_data)
                performance_gaps.append(gap)
                if gap.status == 'CRITICAL_MISREPRESENTATION':
                    conflicts.append(f"[HYPE_ALERT] {gap.metric}: 이론적 근거({gap.sci_val}) 대비 {gap.hype_index}배 과장 감지.")
            
            # 2. 서술적 모순/왜곡 처리 (판단 근거를 conflicts에 직접 추가)
            for nc in data.get("narrative_conflicts", []):
                conflicts.append(f"[NARRATIVE_MISMATCH] {nc}")
                
        except Exception as e:
            conflicts.append(f"[ANALYSIS_ERR] 교차 분석 실패: {str(e)}")

        # [Step 4] 최종 게이트키핑
        critical_hype = any(g.status == 'CRITICAL_MISREPRESENTATION' for g in performance_gaps)
        high_reg_risk = any(rc.severity == 'HIGH' for rc in regulatory_conflicts)

        # 요약 문자열 리스트(conflicts) 보완
        for rc in regulatory_conflicts:
            if rc.severity == 'HIGH':
                conflicts.append(f"[REG_CRITICAL] {rc.description}: {rc.analyst_note}")
        
        for pg in performance_gaps:
            if pg.status == 'Hype Warning' and f"[{pg.metric}]" not in "".join(conflicts):
                conflicts.append(f"[HYPE_WARNING] {pg.metric}: {pg.description}")

        for claim in claims:
            # 기존: GRADE가 LOW면 무조건 '판단 보류'로 빠지는 경향이 있었음.
            # 변경: LOW GRADE라도 Evidence Pack(실제 연구 내역)이 존재한다면 비교 대상으로 활용.
            is_fake = critical_hype or (high_reg_risk and (scientific.overall_grade == 'LOW' or industrial.overall_level == 'LOW'))

            if is_fake:
                fake_claims.append(claim)
                verdict, credibility = '검증 실패 (허구/왜곡 의심)', 'LOW'
            else:
                credibility = combine_credibility(scientific.overall_grade, industrial.overall_level)
                
                # Scientific/Industrial 에이전트가 최소한의 결과(LOW GRADE 포함)라도 가져왔다면 비교 대상으로 인정
                has_sci_evidence = len(scientific.papers) > 0
                has_ind_evidence = len(industrial.news) > 0 or len(industrial.patents) > 0
                
                if has_sci_evidence and has_ind_evidence:
                    verdict = '조건부 가능'
                elif not has_sci_evidence and not has_ind_evidence:
                    verdict = '판단 보류 (근거 부족)'
                else:
                    # 한쪽 근거만 있는 경우
                    verdict = '조건부 가능 (단측 근거)'

            results.append(
                ClaimVerificationResult(
                    claim=claim, 
                    credibility=credibility, 
                    verdict=verdict,
                    flags=['HYPE_DETECTED'] if critical_hype else (['REGULATORY_RISK'] if high_reg_risk else [])
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
