from typing import Literal

from pydantic import BaseModel

from .agent_result import (
    CitationMetadataItem,
    CrossValidationResult,
    IndustrialResult,
    RegulatoryResult,
    ReportOutput,
    ScientificResult,
)
from .claim import Claim


class VerificationRequest(BaseModel):
    input_type: Literal['url', 'text', 'title']
    content: str


class VerificationResponse(BaseModel):
    report_markdown: str
    claims: list[Claim]
    scientific: ScientificResult
    industrial: IndustrialResult
    regulatory: RegulatoryResult
    cross_validation: CrossValidationResult
    citation_metadata: list[CitationMetadataItem] = []
    pdf_path: str | None = None


class ReportResponse(ReportOutput):
    pass
