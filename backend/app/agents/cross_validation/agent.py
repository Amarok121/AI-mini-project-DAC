"""CrossValidator 에이전트 진입점: LangChain `cross_validator_chain` 래퍼."""

from __future__ import annotations

from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)

from .lc_chain import cross_validator_chain

async def run(
    claims: list[Claim],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
) -> CrossValidatorOutput:
    """
    [CVA 최종 구현: Evidence Pack 기반 검증]
    앞선 에이전트들이 제공한 '완벽한' Evidence Pack을 대조하여 
    Hype Index(2.0x 룰), 조건 누락, 규제 충돌을 판정합니다.
    """
    return await cross_validator_chain.ainvoke({
        "claims": claims,
        "scientific": scientific,
        "industrial": industrial,
        "regulatory": regulatory
    })
