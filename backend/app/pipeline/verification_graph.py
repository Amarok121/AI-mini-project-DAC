from app.schemas.api import VerificationRequest, VerificationResponse
from app.schemas.claim import Claim
from app.schemas.report import ReportInput
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)
from app.preprocessing.input_parser import parse_input
from app.preprocessing.text_cleaner import clean_text
from app.services.rag_retriever import get_context_string
from app.pipeline.state import VerificationState

# Keep module-level names so tests can monkeypatch them without importing heavy agent modules eagerly.
run_claim_extractor = None
run_scientific = None
run_industrial = None
run_regulatory = None
run_cross_validation = None
generate_report = None


class _SequentialVerificationGraph:
    async def ainvoke(self, state: VerificationState) -> VerificationState:
        current_state = dict(state)
        for node in [
            preprocess_node,
            extract_claims_node,
            validate_agents_node,
            cross_validate_node,
            fetch_company_context_node,
            report_node,
        ]:
            update = await node(current_state)
            current_state.update(update)
        return current_state


async def preprocess_node(state: VerificationState) -> VerificationState:
    # Node 1: request -> raw text -> cleaned text
    raw_text = await parse_input(state["request"].input_type, state["request"].content)
    return {"raw_text": raw_text, "text": clean_text(raw_text)}


async def extract_claims_node(state: VerificationState) -> VerificationState:
    # Node 2: cleaned text -> structured claims
    claims = await _get_run_claim_extractor()(state["text"])
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
    cross = await _get_run_cross_validation()(
        state["claims"],
        state["scientific"],
        state["industrial"],
        state["regulatory"],
    )
    return {"cross_validation": cross}


async def fetch_company_context_node(state: VerificationState) -> VerificationState:
    company_name = 'SK이노베이션'
    try:
        company_context = await get_context_string(f'{company_name} 사업 현황 기술')
    except Exception:
        company_context = ''

    try:
        company_context_section6 = await get_context_string(f'{company_name} R&D 설비 인프라 생산')
    except Exception:
        company_context_section6 = ''

    return {
        'company_context': company_context or '',
        'company_context_section6': company_context_section6 or '',
    }


async def report_node(state: VerificationState) -> VerificationState:
    # TODO: state.py에도 citation_metadata, pdf_path를 명시적으로 추가해 두는 편이 좋습니다.
    report_input = ReportInput(
        scientific_result=state["scientific"],
        industrial_result=state["industrial"],
        regulatory_result=state["regulatory"],
        cross_validation_result=state["cross_validation"],
        original_claims=state["claims"],
        company_name='SK이노베이션',
        company_context=state.get("company_context", ''),
        company_context_section6=state.get("company_context_section6", ''),
    )
    report_output = await _get_generate_report()(
        report_input,
        company_context=state.get("company_context", ''),
        company_context_section6=state.get("company_context_section6", ''),
    )
    report_markdown = report_output.report_markdown
    result = VerificationResponse(
        report_markdown=report_markdown,
        claims=state["claims"],
        scientific=state["scientific"],
        industrial=state["industrial"],
        regulatory=state["regulatory"],
        cross_validation=state["cross_validation"],
        citation_metadata=report_output.citation_metadata,
        pdf_path=report_output.pdf_path,
    )
    return {
        "report_markdown": report_markdown,
        "citation_metadata": report_output.citation_metadata,
        "pdf_path": report_output.pdf_path,
        "result": result,
    }


def build_verification_graph():
    try:
        from langgraph.graph import StateGraph, START, END
    except Exception:
        return _SequentialVerificationGraph()

    graph = StateGraph(VerificationState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("extract_claims", extract_claims_node)
    graph.add_node("validate_agents", validate_agents_node)
    graph.add_node("cross_validate", cross_validate_node)
    graph.add_node("fetch_company_context", fetch_company_context_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "extract_claims")
    graph.add_edge("extract_claims", "validate_agents")
    graph.add_edge("validate_agents", "cross_validate")
    graph.add_edge("cross_validate", "fetch_company_context")
    graph.add_edge("fetch_company_context", "report")
    graph.add_edge("report", END)

    return graph.compile()


async def _run_validation_agents(claims: list[Claim]):
    import asyncio

    scientific, industrial, regulatory = await asyncio.gather(
        _run_agent_with_fallback(_get_run_scientific, claims),
        _run_agent_with_fallback(_get_run_industrial, claims),
        _run_agent_with_fallback(_get_run_regulatory, claims),
        return_exceptions=True,
    )

    if isinstance(scientific, Exception):
        scientific = ScientificAgentOutput(error=str(scientific), summary="Scientific agent failed.")
    if isinstance(industrial, Exception):
        industrial = IndustrialAgentOutput(error=str(industrial), summary="Industrial agent failed.")
    if isinstance(regulatory, Exception):
        regulatory = RegulatoryAgentOutput(error=str(regulatory))

    return scientific, industrial, regulatory


async def _run_agent_with_fallback(getter, claims: list[Claim]):
    try:
        runner = getter()
        return await runner(claims)
    except Exception as exc:
        return exc


def _get_run_claim_extractor():
    global run_claim_extractor
    if run_claim_extractor is None:
        from app.agents.claim_extractor import run_claim_extractor as imported

        run_claim_extractor = imported
    return run_claim_extractor


def _get_run_scientific():
    global run_scientific
    if run_scientific is None:
        from app.agents.scientific.agent import run as imported

        run_scientific = imported
    return run_scientific


def _get_run_industrial():
    global run_industrial
    if run_industrial is None:
        from app.agents.industrial.agent import run as imported

        run_industrial = imported
    return run_industrial


def _get_run_regulatory():
    global run_regulatory
    if run_regulatory is None:
        from app.agents.regulatory.agent import run as imported

        run_regulatory = imported
    return run_regulatory


def _get_run_cross_validation():
    global run_cross_validation
    if run_cross_validation is None:
        from app.agents.cross_validation.agent import run as imported

        run_cross_validation = imported
    return run_cross_validation


def _get_generate_report():
    global generate_report
    if generate_report is None:
        from app.agents.report.agent import generate_report as imported

        generate_report = imported
    return generate_report
