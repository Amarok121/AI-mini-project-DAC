from typing import Literal
from pydantic import BaseModel
from .claim import Claim


class PaperResult(BaseModel):
    title: str
    authors: list[str] = []
    year: int = 0
    url: str = ''
    grade_score: float = 0.0
    grade_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    summary: str = ''
    key_point: str = ''
    excerpt: str = ''
    conditions: list[str] = []
    limitations: list[str] = []
    reason: str = ''


class ScientificAgentOutput(BaseModel):
    papers: list[PaperResult] = []
    overall_grade: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    trl_estimate: str = 'TRL 1~3'
    summary: str = ''
    error: str | None = None


class NewsResult(BaseModel):
    title: str
    publisher: str = ''
    published_at: str = ''
    url: str = ''
    craap_score: float = 0.0
    craap_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    summary: str = ''
    excerpt: str = ''
    flags: list[str] = []


class PatentResult(BaseModel):
    title: str
    applicant: str = ''
    application_date: str = ''
    status: str = '등록'
    core_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    summary: str = ''
    key_point: str = ''
    flags: list[str] = []
    url: str = ''


class IndustrialAgentOutput(BaseModel):
    news: list[NewsResult] = []
    patents: list[PatentResult] = []
    overall_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    mrl_estimate: str = 'MRL 1~3'
    summary: str = ''
    error: str | None = None


class RegulatoryAgentOutput(BaseModel):
    verdict: Literal['해당', '미해당', '불명확'] = '불명확'
    confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    applicable_regulations: list[str] = []
    incentives: list[str] = []
    risks: list[str] = []
    requires_expert_review: bool = True
    source_urls: list[str] = []
    error: str | None = None


class ClaimVerificationResult(BaseModel):
    claim: Claim
    credibility: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    verdict: str = '판단 보류'
    flags: list[str] = []
    trl: str = 'TRL 1~3'
    mrl: str = 'MRL 1~3'
    cri: str = 'CRI 1~3'


class PerformanceGapResult(BaseModel):
    metric: str
    sci_val: float
    ind_val: float
    hype_index: float
    status: str
    description: str
    analyst_note: str

class RegulatoryConflictResult(BaseModel):
    conflict_type: str
    severity: str
    description: str
    analyst_note: str

class CrossValidatorOutput(BaseModel):
    """CVA의 최종 분석 결과물"""
    results: list[ClaimVerificationResult] = []
    overall_verdict: str = '판단 보류'
    conflicts: list[str] = []
    performance_gaps: list[PerformanceGapResult] = []
    regulatory_conflicts: list[RegulatoryConflictResult] = []
    fake_claims_detected: list[Claim] = []
