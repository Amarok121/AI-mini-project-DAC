from typing import Literal

from pydantic import BaseModel

from .claim import Claim, ClaimJudgement


AgentStatus = Literal['success', 'error']
ConfidenceLevel = Literal['HIGH', 'MED', 'LOW']
SourceType = Literal['논문', '뉴스', '특허', '법규', '내부문서']
JudgementVerdict = Literal['지지', '반박', '불확실']


class SourceItem(BaseModel):
    ref_id: str = ''
    title: str = ''
    authors: list[str] = []
    year: int = 0
    source_type: SourceType = '논문'
    url: str = ''
    publisher: str = ''
    snippet: str = ''
    apa_citation: str = ''


class AgentResultBase(BaseModel):
    agent_name: str = ''
    status: AgentStatus = 'success'
    error: str | None = None
    summary: str = ''
    confidence: ConfidenceLevel = 'LOW'
    sources: list[SourceItem] = []


class PaperResult(BaseModel):
    title: str
    authors: list[str] = []
    year: int = 0
    journal: str = ''
    url: str = ''
    grade_score: float = 0.0
    grade_level: ConfidenceLevel = 'LOW'


class ScientificResult(AgentResultBase):
    papers: list[PaperResult] = []
    overall_grade: ConfidenceLevel = 'LOW'
    trl_score: int = 1
    trl_estimate: str = 'TRL 1'
    trl_rationale: str = ''


class NewsResult(BaseModel):
    title: str
    provider: str = ''
    published_at: str = ''
    url: str = ''
    craap_score: float = 0.0
    craap_level: ConfidenceLevel = 'LOW'


class PatentResult(BaseModel):
    title: str
    applicant: str = ''
    application_date: str = ''
    status: Literal['등록', '심사중', '출원'] = '출원'
    is_core_tech: bool = False


class IndustrialResult(AgentResultBase):
    news: list[NewsResult] = []
    patents: list[PatentResult] = []
    overall_level: ConfidenceLevel = 'LOW'
    mrl_score: int = 1
    mrl_estimate: str = 'MRL 1'
    mrl_rationale: str = ''


class RegulatoryResult(AgentResultBase):
    verdict: Literal['해당', '미해당', '불명확'] = '불명확'
    applicable_regulations: list[str] = []
    incentives: list[str] = []
    risks: list[str] = []
    requires_expert_review: bool = True
    source_urls: list[str] = []
    cri_score: int = 1
    cri_estimate: str = 'CRI 1'
    cri_rationale: str = ''


class CrossValidationResult(AgentResultBase):
    results: list[ClaimJudgement] = []
    overall_verdict: str = '판단 보류'
    overall_confidence: ConfidenceLevel = 'LOW'
    scientific_confidence: ConfidenceLevel = 'LOW'
    industrial_confidence: ConfidenceLevel = 'LOW'
    regulatory_confidence: ConfidenceLevel = 'LOW'
    conflicts: list[str] = []


class ClaimVerificationResult(BaseModel):
    claim: Claim
    credibility: ConfidenceLevel = 'LOW'
    verdict: str = '판단 보류'
    flags: list[str] = []
    trl: str = 'TRL 1~3'
    mrl: str = 'MRL 1~3'
    cri: str = 'CRI 1~3'


class SectionDraft(BaseModel):
    section_id: str
    title: str
    markdown: str = ''
    ref_ids: list[str] = []
    has_error: bool = False
    error: str | None = None


class CitationMetadataItem(BaseModel):
    ref_id: str
    apa_citation: str = ''
    snippet: str = ''
    url: str = ''
    source_type: SourceType = '논문'


class ReportInput(BaseModel):
    company_name: str
    claims: list[Claim] = []
    scientific: ScientificResult
    industrial: IndustrialResult
    regulatory: RegulatoryResult
    cross_validation: CrossValidationResult


class ReportOutput(BaseModel):
    markdown: str = ''
    report_markdown: str = ''
    section_drafts: list[SectionDraft] = []
    citation_metadata: list[CitationMetadataItem] = []
    pdf_path: str | None = None
    error: str | None = None


# Backward-compatible aliases for the current codebase.
ScientificAgentOutput = ScientificResult
IndustrialAgentOutput = IndustrialResult
RegulatoryAgentOutput = RegulatoryResult
CrossValidatorOutput = CrossValidationResult
