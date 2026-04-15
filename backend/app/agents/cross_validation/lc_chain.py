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
    build_news_specific_evidence,
    build_cross_validation_tools,
    enrich_cross_validation_evidence,
    parse_cross_validation_tool_calls,
    report_contains_english,
    summarize_news_audits,
    validate_news_audits,
    validate_news_audit_paper_titles,
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
        performance_gaps: list[PerformanceGapResult] = []
        narrative_fail = False
        regulatory_conflicts = []
        audit_summary = {
            "total": 0.0,
            "support_ratio": 0.0,
            "refute_ratio": 0.0,
            "supplement_ratio": 0.0,
            "na_paper_ratio": 0.0,
        }

        # [Step 1] Evidence Pack 통합 문맥 생성 (전체 문헌 Full Title 유지)
        evidence_pack_context = "### [Scientific Evidence - Multiple Papers]\n"
        for i, p in enumerate(scientific.papers):
            evidence_pack_context += f"Document Title: {p.title}\n  - Summary: {p.summary}\n  - Conditions: {p.conditions}\n  - Limitations: {p.limitations}\n"

        evidence_pack_context += "\n### [Industrial Evidence - News & Patents]\n"
        industrial_count = 0
        for i, n in enumerate(industrial.news):
            evidence_pack_context += f"Industrial Item {i+1}. Title: {n.title}\n  - Summary: {n.summary}\n  - Flags: {n.flags}\n"
            industrial_count += 1
        for i, pt in enumerate(industrial.patents):
            evidence_pack_context += f"Industrial Item {industrial_count+i+1}. Title: {pt.title}\n  - Status: {pt.status}\n  - Summary: {pt.summary}\n  - Key Point: {pt.key_point}\n"
            industrial_count += 1

        evidence_pack_context += "\n### [Regulatory & Legal Evidence]\n"
        evidence_pack_context += f"- Verdict: {regulatory.verdict}\n"
        evidence_pack_context += f"- Confidence: {regulatory.confidence}\n"
        evidence_pack_context += f"- Applicable Regulations: {regulatory.applicable_regulations}\n"
        evidence_pack_context += f"- Risks: {regulatory.risks}\n"
        evidence_pack_context += f"- Incentives: {regulatory.incentives}\n"
        evidence_pack_context += f"- Regulatory Summary: {regulatory.evidence_summary}\n"

        # [Step 2] Tool 정의 (LLM이 단일 구조 결과를 제출)
        tools = build_cross_validation_tools()

        claims_dict = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in claims]
        prompt = f"""
        당신은 산업계의 기술적 거품을 걷어내는 '최종 감사관'입니다. 
        제시된 **{industrial_count}건의 모든 산업계 데이터**를 전수 조사하고, 각 항목의 성격에 맞는 도구(Tool)를 선택하여 호출하십시오.

        [사용자 클레임]
        {json.dumps(claims_dict, ensure_ascii=False)}

        [Evidence Pack]
        {evidence_pack_context}

        [분석 지침]
        1. `conflicts`에는 뉴스/특허의 주장과 논문 근거를 대조해 옳고 그름을 판정한 내용을 작성하십시오.
           각 항목에는 반드시 근거 문구를 포함하십시오(예: 논문 제목/뉴스 제목/핵심 발췌).
        1-1. `news_audits`의 각 뉴스 항목마다 `scientific.papers` 전체를 검토한 뒤,
             문맥상 가장 관련성 높은 논문 1편을 선택하거나 적합 논문이 없으면 `matched_paper_title`을 반드시 `N/A`로 기록하십시오.
        1-2. 약어/용어가 다의적인 경우(예: 동일 약어가 다른 기술 영역 의미를 가질 수 있음),
             제목/요약/발췌 문맥을 근거로 의미를 먼저 판별하고 그 판별 근거를 `matched_paper_reason`에 명시하십시오.
        1-3. `matched_paper_title`은 제공된 scientific 논문 제목 중 정확히 일치하는 값 또는 `N/A`만 허용됩니다.
        1-4. 뉴스 평가는 claim 직접 입증 여부가 아니라, 뉴스 내용과 논문 근거의 정합성/맥락 적합성을 평가합니다.
        2. `performance_gaps`에는 수치형 비교가 가능한 경우에만 뉴스/특허 수치와 논문 실험 수치를 비교해 작성하십시오.
        3. `regulatory_conflicts`에는 규제/특허와 claim 기술의 정합성 판단을 작성하십시오.
           `analyst_note`에 반드시 규제명/리스크/문서 근거를 포함하십시오.
        3-1. `tech_status`와 `final_verdict`는 모든 news_audits + scientific/regulatory를 종합한 기술 평가를 작성하십시오.
        4. 최종 결과는 반드시 `submit_cross_validation_report` 도구 1회 호출로 제출하십시오.
        """

        try:
            messages = [
                {"role": "system", "content": "당신은 도구를 사용하여 정밀 기술 감사를 수행하는 전문가입니다. 모든 출력은 한국어로 작성하십시오."},
                {"role": "user", "content": prompt},
            ]
            llm_conflicts: list[str] = []
            llm_news_audits: list[dict[str, str]] = []
            llm_performance_gaps = []
            llm_regulatory_conflicts = []
            llm_tech_status = ""
            llm_final_verdict = ""

            for _ in range(2):
                response = await openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice={"type": "function", "function": {"name": "submit_cross_validation_report"}},
                )
                tool_calls = response.choices[0].message.tool_calls or []
                (
                    llm_conflicts,
                    llm_news_audits,
                    llm_performance_gaps,
                    llm_regulatory_conflicts,
                    llm_tech_status,
                    llm_final_verdict,
                    narrative_fail,
                ) = parse_cross_validation_tool_calls(tool_calls)

                is_complete, missing_news = validate_news_audits(llm_news_audits, industrial)
                paper_links_valid, invalid_paper_links = validate_news_audit_paper_titles(
                    llm_news_audits,
                    scientific,
                )
                has_english = report_contains_english(
                    llm_conflicts,
                    llm_news_audits,
                    llm_regulatory_conflicts,
                )
                if is_complete and paper_links_valid and not has_english:
                    break
                retry_reason = []
                if not is_complete:
                    retry_reason.append(f"누락 뉴스: {missing_news}")
                if not paper_links_valid:
                    retry_reason.append(f"논문 매칭 오류: {invalid_paper_links}")
                if has_english:
                    retry_reason.append("출력에 영문 문구가 포함됨")
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "이전 응답을 수정해서 다시 제출하세요. "
                            f"수정 사유: {', '.join(retry_reason)}. "
                            "news_audits에 모든 뉴스를 포함하고, matched_paper_title은 제공된 논문 제목 또는 N/A만 사용하세요. "
                            "conflicts/regulatory_conflicts/news_audits는 한국어로만 작성하세요."
                        ),
                    }
                )

            conflicts.extend(llm_conflicts)
            for item in llm_news_audits:
                source_evidence = build_news_specific_evidence(
                    item["news_title"],
                    scientific,
                    industrial,
                    item.get("matched_paper_title", ""),
                    item.get("matched_paper_reason", ""),
                )
                conflicts.append(
                    f"뉴스 평가: '{item['news_title']}' -> {item['verdict']}. "
                    f"판단: {item['reason']}. 근거: {item['evidence']}. 자료: {source_evidence}"
                )
            if llm_tech_status:
                conflicts.append(f"기술 평가: {llm_tech_status}")
            if llm_final_verdict:
                conflicts.append(f"최종 판단 근거: {llm_final_verdict}")

            performance_gaps.extend(llm_performance_gaps)
            regulatory_conflicts.extend(llm_regulatory_conflicts)

            is_complete, missing_news = validate_news_audits(llm_news_audits, industrial)
            if not is_complete:
                conflicts.append(f"[ANALYSIS_WARN] 누락 뉴스 평가: {missing_news}")
            paper_links_valid, invalid_paper_links = validate_news_audit_paper_titles(llm_news_audits, scientific)
            if not paper_links_valid:
                conflicts.append(f"[ANALYSIS_WARN] 뉴스-논문 매칭 오류: {invalid_paper_links}")
            audit_summary = summarize_news_audits(llm_news_audits)
            if audit_summary["total"] > 0 and audit_summary["na_paper_ratio"] >= 0.7:
                conflicts.append("[ANALYSIS_WARN] 다수 뉴스가 N/A 매핑입니다. 논문 커버리지 확장이 필요할 수 있습니다.")
            if report_contains_english(conflicts, llm_news_audits, regulatory_conflicts):
                conflicts.append("[ANALYSIS_WARN] 일부 영문 문구가 남아 있습니다. 한국어 재검토가 필요합니다.")
            if not llm_conflicts and not llm_news_audits and not llm_regulatory_conflicts:
                conflicts.append("[ANALYSIS_WARN] LLM이 구조화 결과를 반환하지 않아 세부 검증 결과가 비어 있습니다.")

            conflicts, regulatory_conflicts = enrich_cross_validation_evidence(
                conflicts,
                regulatory_conflicts,
                scientific,
                industrial,
                regulatory,
            )
        except Exception as e:
            conflicts.append(f"[ANALYSIS_ERR] 도구 기반 교차 분석 실패: {str(e)}")

        # [Step 3] 최종 게이트키핑
        critical_hype = any(g.status == 'CRITICAL_MISREPRESENTATION' for g in performance_gaps)
        high_reg_risk = any(rc.severity == 'HIGH' for rc in regulatory_conflicts)

        # 요약 리스트 보완 (규제 등)
        for rc in regulatory_conflicts:
            if rc.severity == 'HIGH':
                conflicts.append(f"[REG_CRITICAL] {rc.description}: {rc.analyst_note}")
            elif rc.severity == 'MED':
                conflicts.append(f"[REG_NOTE] {rc.description}: {rc.analyst_note}")
        
        for pg in performance_gaps:
            if pg.status == 'Hype Warning' and f"[{pg.metric}]" not in "".join(conflicts):
                conflicts.append(f"[HYPE_WARNING] {pg.metric}: {pg.description}")

        for claim in claims:
            is_fake = critical_hype or narrative_fail or (high_reg_risk and (scientific.overall_grade == 'LOW' or industrial.overall_level == 'LOW'))

            if is_fake:
                fake_claims.append(claim)
                verdict, credibility = '검증 실패 (허구/왜곡 의심)', 'LOW'
            else:
                credibility = combine_credibility(scientific.overall_grade, industrial.overall_level)
                
                has_sci_evidence = len(scientific.papers) > 0
                has_ind_evidence = len(industrial.news) > 0 or len(industrial.patents) > 0
                
                if has_sci_evidence and has_ind_evidence:
                    if audit_summary.get("refute_ratio", 0.0) >= 0.5:
                        verdict = '주의 필요 (상충 근거 존재)'
                    else:
                        verdict = '조건부 가능'
                elif has_sci_evidence:
                    verdict = '조건부 가능'
                elif not has_sci_evidence and not has_ind_evidence:
                    verdict = '판단 보류 (근거 부족)'
                else:
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
            overall_verdict=(
                '주의 요망'
                if fake_claims or critical_hype or high_reg_risk or narrative_fail
                else ('주의 요망' if audit_summary.get("refute_ratio", 0.0) >= 0.5 else '조건부 가능')
            ),
            conflicts=conflicts,
            performance_gaps=performance_gaps,
            regulatory_conflicts=regulatory_conflicts,
            fake_claims_detected=fake_claims
        )

cross_validator_chain = CrossValidatorChain()
