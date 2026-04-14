
import asyncio
import json
import os
import sys

# 프로젝트 루트를 path에 추가하여 app 모듈을 찾을 수 있게 함
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.agents.cross_validation.agent import run
from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    PaperResult,
    IndustrialAgentOutput,
    NewsResult,
    PatentResult,
    RegulatoryAgentOutput
)

async def test_cross_validator():
    print("=== CrossValidator Dummy Test ===")

    # 1. Dummy Claims
    claims = [
        Claim(
            technology="DAC (Direct Air Capture)",
            claim="연간 10만 톤의 CO2를 포집하며, 포집 비용은 톤당 $100 미만이다.",
            application="상용 탄소 포집 플랜트"
        )
    ]

    # 2. Dummy Scientific Output (논문 근거)
    # 실제 연구는 실험실 수준이며 비용은 $300-$500 사이로 언급됨
    scientific = ScientificAgentOutput(
        overall_grade="MED",
        papers=[
            PaperResult(
                title="Lab-scale Evaluation of Novel Sorbents for Direct Air Capture",
                year=2024,
                url="https://example.org/paper1",
                grade_level="HIGH",
                summary="실험실 환경에서 새로운 흡착제의 성능을 평가함. 이론적으로 대규모화 시 비용 절감이 가능하나 현재는 톤당 $400 수준임.",
                excerpt="Our results show a theoretical lower bound of $350/ton-CO2 under optimized conditions.",
                conditions=["Lab-scale", "Nitrogen-purged environment"],
                limitations=["Scale-up effects not yet verified", "High energy consumption"]
            )
        ],
        summary="실험실 수준의 연구 결과이며, 대규모 상용화 시의 비용 데이터는 아직 부족함."
    )

    # 3. Dummy Industrial Output (뉴스/특허 근거)
    # 기사는 매우 낙관적이며 $90 달성 주장
    industrial = IndustrialAgentOutput(
        overall_level="HIGH",
        news=[
            NewsResult(
                title="EcoCapture Inc. Announces Breakthrough: $90/ton Carbon Capture is Here",
                url="https://news.example.com/dac-breakthrough",
                summary="EcoCapture사는 독자적인 기술로 톤당 $90의 포집 비용을 달성했다고 발표함. 연내 10만 톤 규모 플랜트 가동 예정.",
                excerpt="We have achieved the holy grail of carbon capture: sub-$100 costs.",
                craap_level="MED"
            )
        ],
        patents=[
            PatentResult(
                title="System and method for large-scale direct air capture",
                status="출원",
                summary="대규모 DAC 시스템 설계에 관한 특허. 효율 개선을 위한 공정 설계 포함."
            )
        ],
        mrl_estimate="MRL 5~6"
    )

    # 4. Dummy Regulatory Output (규제/인센티브)
    regulatory = RegulatoryAgentOutput(
        verdict="해당",
        confidence="HIGH",
        incentives=["IRA 45Q Tax Credit ($180/ton for DAC)"],
        risks=["국내 탄소배출권 거래제(K-ETS) 가격 변동 리스크"],
        applicable_regulations=["탄소중립기본법"],
        evidence_summary="미국 IRA 45Q 세액 공제 혜택을 받을 수 있어 경제성 확보에 유리함."
    )

    # 실행
    result = await run(claims, scientific, industrial, regulatory)

    # 결과 출력
    print("\n--- Verification Results ---")
    print(f"Overall Verdict: {result.overall_verdict}")
    
    print("\n[Conflicts]")
    for c in result.conflicts:
        print(f"- {c}")

    print("\n[Individual Claim Results]")
    for r in result.results:
        print(f"- Claim: {r.claim.claim}")
        print(f"  Verdict: {r.verdict}")
        print(f"  Credibility: {r.credibility}")
        print(f"  Flags: {r.flags}")

    print("\n[Performance Gaps]")
    for g in result.performance_gaps:
        print(f"- Metric: {g.metric}")
        print(f"  Hype Index: {g.hype_index}")
        print(f"  Status: {g.status}")
        print(f"  Analyst Note: {g.analyst_note}")

    print("\n[Regulatory Conflicts]")
    for rc in result.regulatory_conflicts:
        print(f"- Type: {rc.conflict_type}")
        print(f"  Description: {rc.description}")
        print(f"  Analyst Note: {rc.analyst_note}")

if __name__ == "__main__":
    asyncio.run(test_cross_validator())
