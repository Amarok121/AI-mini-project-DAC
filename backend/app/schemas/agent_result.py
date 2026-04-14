from typing import Literal, Optional
from pydantic import BaseModel
from .claim import Claim


class PaperResult(BaseModel):
    title: str
    authors: list[str] = []
    year: int = 0
    journal: str = ''
    url: str = ''
    grade_score: float = 0.0
    grade_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'


class ScientificAgentOutput(BaseModel):
    papers: list[PaperResult] = []
    overall_grade: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    trl_estimate: str = 'TRL 1~3'
    summary: str = ''
    error: Optional[str] = None


class NewsResult(BaseModel):
    title: str
    provider: str = ''
    published_at: str = ''
    url: str = ''
    craap_score: float = 0.0
    craap_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'


class PatentResult(BaseModel):
    title: str
    applicant: str = ''
    application_date: str = ''
    status: Literal['등록', '심사중', '출원'] = '출원'
    is_core_tech: bool = False


class IndustrialAgentOutput(BaseModel):
    news: list[NewsResult] = []
    patents: list[PatentResult] = []
    overall_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    mrl_estimate: str = 'MRL 1~3'
    summary: str = ''
    error: Optional[str] = None


class RegulatoryAgentOutput(BaseModel):
    verdict: Literal['해당', '미해당', '불명확'] = '불명확'
    confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    applicable_regulations: list[str] = []
    incentives: list[str] = []
    risks: list[str] = []
    requires_expert_review: bool = True
    source_urls: list[str] = []
    error: Optional[str] = None
    # 파이프라인(Tavily → 법령 추출 → 포털 → LLM) 보강 필드
    reason: Optional[str] = None
    extracted_law_candidates: list[str] = []
    pipeline_notes: list[str] = []


class ClaimVerificationResult(BaseModel):
    claim: Claim
    credibility: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    verdict: str = '판단 보류'
    flags: list[str] = []
    trl: str = 'TRL 1~3'
    mrl: str = 'MRL 1~3'
    cri: str = 'CRI 1~3'


class CrossValidatorOutput(BaseModel):
    results: list[ClaimVerificationResult] = []
    overall_verdict: str = '판단 보류'
    conflicts: list[str] = []
