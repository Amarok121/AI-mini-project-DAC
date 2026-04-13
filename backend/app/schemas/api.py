from typing import Literal
from pydantic import BaseModel
from .claim import Claim
from .agent_result import (
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    CrossValidatorOutput,
)


class VerificationRequest(BaseModel):
    input_type: Literal['url', 'text', 'title']
    content: str


class VerificationResponse(BaseModel):
    report_markdown: str
    claims: list[Claim]
    scientific: ScientificAgentOutput
    industrial: IndustrialAgentOutput
    regulatory: RegulatoryAgentOutput
    cross_validation: CrossValidatorOutput
