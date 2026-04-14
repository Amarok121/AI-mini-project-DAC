"""Scientific 에이전트 진입점: LangChain `scientific_chain` 래퍼."""

from __future__ import annotations

from app.schemas.claim import Claim
from app.schemas.agent_result import ScientificAgentOutput

from app.agents.scientific.lc_chain import scientific_chain


async def run(claims: list[Claim]) -> ScientificAgentOutput:
    return await scientific_chain.ainvoke({"claims": claims})
