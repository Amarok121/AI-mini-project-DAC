from app.schemas.claim import Claim
from app.schemas.agent_result import RegulatoryAgentOutput


async def run(claims: list[Claim]) -> RegulatoryAgentOutput:
    # TODO: Tavily -> 공식 법령 원문 fetch -> 적용성 판단 파이프라인 구현
    return RegulatoryAgentOutput(
        verdict='불명확',
        confidence='MED',
        applicable_regulations=['탄소중립기본법'],
        incentives=['국내 실증지원 가능성 검토 필요'],
        risks=['해외 인센티브(IRA) 적용 조건 미확정'],
        requires_expert_review=True,
        source_urls=['https://www.law.go.kr'],
    )
