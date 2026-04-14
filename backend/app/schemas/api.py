from typing import Literal, Optional

from pydantic import BaseModel

from .agent_result import (
    CrossValidationResult,
    IndustrialResult,
    RegulatoryResult,
    ScientificResult,
)
from .claim import Claim
from .report import ChartData, CitationMeta, ReportOutput


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
    citation_metadata: list[CitationMeta] = []
    chart_data: Optional[ChartData] = None
    pdf_path: Optional[str] = None


class ReportResponse(ReportOutput):
    pass
