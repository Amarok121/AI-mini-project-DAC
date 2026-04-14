from app.schemas.api import VerificationRequest, VerificationResponse
from .verification_graph import build_verification_graph


async def run_verification(request: VerificationRequest) -> VerificationResponse:
    graph = build_verification_graph()
    state = await graph.ainvoke({"request": request})
    result = state.get("result")
    if result is None:
        raise RuntimeError("LangGraph execution finished without a result")
    return result
