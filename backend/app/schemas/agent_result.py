from typing import Literal, Optional

from pydantic import BaseModel, Field

from .claim import Claim, ClaimJudgement
from .source import SourceItem


AgentStatus = Literal['success', 'error']
ConfidenceLevel = Literal['HIGH', 'MED', 'LOW']
JudgementVerdict = Literal['지지', '반박', '불확실']


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
    citation_count: int = 0
    abstract: str = ''
    semantic_scholar_id: str = ''
    openalex_id: str = ''
    arxiv_id: str = ''
    doi: str = ''


class GradeDimensionScores(BaseModel):
    study_design: float = Field(0.0, description='연구 설계 수준')
    bias_risk: float = Field(0.0, description='편향 위험 (높을수록 양호)')
    consistency_hint: float = Field(0.0, description='인용·일관성 힌트 (OpenAlex 등)')
    directness: float = Field(0.0, description='실제 적용 조건과의 근접도 (휴리스틱)')
    precision_hint: float = Field(0.0, description='표본·인용 규모 힌트')
    venue_authority: float = Field(0.0, description='저널·출처 권위 휴리스틱')
    weighted_total: float = Field(0.0, description='가중 합산')


class ScientificResult(AgentResultBase):
    papers: list[PaperResult] = []
    overall_grade: ConfidenceLevel = 'LOW'
    trl_score: int = 1
    trl_estimate: str = 'TRL 1~3'
    trl_rationale: str = ''
    grade_breakdown: Optional[GradeDimensionScores] = None
    search_sources: list[str] = Field(default_factory=list)


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
    mrl_estimate: str = 'MRL 1~3'
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
    reason: Optional[str] = None
    extracted_law_candidates: list[str] = []
    pipeline_notes: list[str] = []


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


ScientificAgentOutput = ScientificResult
IndustrialAgentOutput = IndustrialResult
RegulatoryAgentOutput = RegulatoryResult
CrossValidatorOutput = CrossValidationResult
