from app.schemas.api import VerificationRequest, VerificationResponse
from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)
from app.preprocessing.input_parser import parse_input
from app.preprocessing.text_cleaner import clean_text
from app.agents.claim_extractor import run_claim_extractor
from app.agents.scientific.agent import run as run_scientific
from app.agents.industrial.agent import run as run_industrial
from app.agents.regulatory.agent import run as run_regulatory
from app.agents.cross_validation.agent import run as run_cross_validation
from app.agents.report.agent import run as run_report
from app.pipeline.state import VerificationState

from langgraph.graph import StateGraph, START, END


async def preprocess_node(state: VerificationState) -> VerificationState:
    # Node 1: request -> raw text -> cleaned text
    raw_text = await parse_input(state["request"].input_type, state["request"].content)
    return {"raw_text": raw_text, "text": clean_text(raw_text)}


async def extract_claims_node(state: VerificationState) -> VerificationState:
    # Node 2: cleaned text -> structured claims
    claims = await run_claim_extractor(state["text"])
    return {"claims": claims}


async def validate_agents_node(state: VerificationState) -> VerificationState:
    # Node 3: run scientific / industrial / regulatory in parallel
    scientific, industrial, regulatory = await _run_validation_agents(state["claims"])
    return {
        "scientific": scientific,
        "industrial": industrial,
        "regulatory": regulatory,
    }


async def cross_validate_node(state: VerificationState) -> VerificationState:
    # Node 4: combine agent outputs and detect conflicts
    cross = await run_cross_validation(
        state["claims"],
        state["scientific"],
        state["industrial"],
        state["regulatory"],
    )
    return {"cross_validation": cross}


async def report_node(state: VerificationState) -> VerificationState:
    # Node 5: final narrative report + response payload
    report_markdown = await run_report(
        state["claims"],
        state["scientific"],
        state["industrial"],
        state["regulatory"],
        state["cross_validation"],
    )
    result = VerificationResponse(
        report_markdown=report_markdown,
        claims=state["claims"],
        scientific=state["scientific"],
        industrial=state["industrial"],
        regulatory=state["regulatory"],
        cross_validation=state["cross_validation"],
    )
    return {"report_markdown": report_markdown, "result": result}


def build_verification_graph():
    # Linear graph: preprocess -> extract -> validate -> cross-validate -> report
    graph = StateGraph(VerificationState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("extract_claims", extract_claims_node)
    graph.add_node("validate_agents", validate_agents_node)
    graph.add_node("cross_validate", cross_validate_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "extract_claims")
    graph.add_edge("extract_claims", "validate_agents")
    graph.add_edge("validate_agents", "cross_validate")
    graph.add_edge("cross_validate", "report")
    graph.add_edge("report", END)

    return graph.compile()


async def _run_validation_agents(claims: list[Claim]):
    import asyncio

    scientific, industrial, regulatory = await asyncio.gather(
        run_scientific(claims),
        run_industrial(claims),
        run_regulatory(claims),
        return_exceptions=True,
    )

    if isinstance(scientific, Exception):
        scientific = ScientificAgentOutput(error=str(scientific), summary="Scientific agent failed.")
    if isinstance(industrial, Exception):
        industrial = IndustrialAgentOutput(error=str(industrial), summary="Industrial agent failed.")
    if isinstance(regulatory, Exception):
        regulatory = RegulatoryAgentOutput(error=str(regulatory))

    return scientific, industrial, regulatory
