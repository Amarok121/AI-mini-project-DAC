from __future__ import annotations

from typing import TypedDict

from app.schemas.api import VerificationRequest, VerificationResponse
from app.schemas.claim import Claim
from app.schemas.agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)


class VerificationState(TypedDict, total=False):
    # Graph input
    request: VerificationRequest
    # Preprocessing outputs
    raw_text: str
    text: str
    # Claim extraction output
    claims: list[Claim]
    # Parallel validation outputs
    scientific: ScientificAgentOutput
    industrial: IndustrialAgentOutput
    regulatory: RegulatoryAgentOutput
    # Aggregation outputs
    cross_validation: CrossValidatorOutput
    company_context: str
    company_context_section6: str
    pdf_path: str
    citation_metadata: list  # list[CitationMeta], schemas/report.py 참고
    report_markdown: str
    result: VerificationResponse
