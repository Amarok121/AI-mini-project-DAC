from typing import Literal, Optional

from pydantic import BaseModel, Field

from .claim import Claim, ClaimJudgement
from .source import SourceItem


AgentStatus = Literal['success', 'error']
ConfidenceLevel = Literal['HIGH', 'MED', 'LOW']


class AgentResultBase(BaseModel):
    agent_name: str = ''
    status: AgentStatus = 'success'
    error: str | None = None
    summary: str = ''
    confidence: ConfidenceLevel = 'LOW'
    sources: list[SourceItem] = Field(default_factory=list)


class SelectedPaperDocument(BaseModel):
    """교차검증·외부 파서로 넘길 선정 논문 참조(바이너리는 전달하지 않고 URL만)."""

    title: str
    primary_url: str = ''
    pdf_url: str = ''
    doi: str = ''
    semantic_scholar_id: str = ''
    openalex_id: str = ''
    arxiv_id: str = ''
    source_system: str = Field(default='', description='semantic_scholar | arxiv | openalex | merged')


class SelectedRegulatoryDocument(BaseModel):
    """교차검증·외부 파서로 넘길 규제·법령 문서 참조."""

    law_name: str = ''
    primary_url: str = ''
    pdf_url: str = ''
    source: str = Field(default='', description='law.go.kr | eur-lex | federalregister.gov 등')


class RegulatoryEvidenceItem(BaseModel):
    """
    규제/인센티브 근거 팩 아이템.
    논문 evidence(`PaperResult`)와 동일하게 요약/발췌/조건/한계/사유를 포함한다.
    """

    title: str = ''
    url: str = ''
    pdf_url: str = ''
    source: str = ''
    published_at: str = ''
    summary: str = ''
    excerpt: str = ''
    key_point: str = ''
    conditions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    reason: str = ''


class PaperResult(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int = 0
    journal: str = Field(default='', exclude=True)
    url: str = ''
    pdf_url: str = Field(default='', exclude=True)
    grade_score: float = 0.0
    grade_level: ConfidenceLevel = 'LOW'
    citation_count: int = Field(default=0, exclude=True)
    abstract: str = Field(default='', exclude=True)
    semantic_scholar_id: str = Field(default='', exclude=True)
    openalex_id: str = Field(default='', exclude=True)
    arxiv_id: str = Field(default='', exclude=True)
    doi: str = Field(default='', exclude=True)
    summary: str = ''
    excerpt: str = ''
    key_point: str = ''
    conditions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason: str = ''


class GradeDimensionScores(BaseModel):
    study_design: float = Field(0.0, description='연구 설계 수준')
    bias_risk: float = Field(0.0, description='편향 위험 (높을수록 양호)')
    consistency_hint: float = Field(0.0, description='인용·일관성 힌트 (OpenAlex 등)')
    directness: float = Field(0.0, description='실제 적용 조건과의 근접도 (휴리스틱)')
    precision_hint: float = Field(0.0, description='표본·인용 규모 힌트')
    venue_authority: float = Field(0.0, description='저널·출처 권위 휴리스틱')
    weighted_total: float = Field(0.0, description='가중 합산')


class ScientificResult(AgentResultBase):
    papers: list[PaperResult] = Field(default_factory=list)
    overall_grade: ConfidenceLevel = 'LOW'
    trl_score: int = 1
    trl_estimate: str = 'TRL 1~3'
    trl_rationale: str = ''
    grade_breakdown: Optional[GradeDimensionScores] = None
    search_sources: list[str] = Field(default_factory=list)


class NewsEvaluationBreakdown(BaseModel):
    currency: float = 0.0
    relevance: float = 0.0
    authority: float = 0.0
    accuracy: float = 0.0
    purpose: float = 0.0


class NewsEvaluation(BaseModel):
    score: float = 0.0
    grade: ConfidenceLevel = 'LOW'
    breakdown: NewsEvaluationBreakdown = Field(default_factory=NewsEvaluationBreakdown)
    flags: list[str] = Field(default_factory=list)
    verdict: str = ''
    reason: str = ''


class NewsEvidenceNarrative(BaseModel):
    summary: str = ''
    excerpt: str = ''
    note: str = ''


class NewsResult(BaseModel):
    title: str
    publisher: str = ''
    published_at: str = ''
    url: str = ''
    excerpt: str = ''
    summary: str = ''
    craap_score: float = 0.0
    craap_level: ConfidenceLevel = 'LOW'
    flags: list[str] = Field(default_factory=list)
    verdict: str = ''
    reason: str = ''
    evaluation: NewsEvaluation = Field(default_factory=NewsEvaluation)


class PatentEvaluationBreakdown(BaseModel):
    search_match: float = 0.0
    legal_status: float = 0.0
    citation_signal: float = 0.0
    specificity: float = 0.0


class PatentEvaluation(BaseModel):
    score: float = 0.0
    grade: ConfidenceLevel = 'LOW'
    breakdown: PatentEvaluationBreakdown = Field(default_factory=PatentEvaluationBreakdown)
    flags: list[str] = Field(default_factory=list)
    verdict: str = ''
    reason: str = ''


class PatentEvidenceNarrative(BaseModel):
    summary: str = ''
    excerpt: str = ''
    key_point: str = ''
    note: str = ''


class PatentResult(BaseModel):
    title: str
    applicant: str = ''
    application_date: str = ''
    status: Literal['등록', '심사중', '출원'] = '출원'
    is_core_tech: bool = False
    url: str = ''
    excerpt: str = ''
    summary: str = ''
    key_point: str = ''
    core_score: float = 0.0
    core_level: ConfidenceLevel = 'LOW'
    flags: list[str] = Field(default_factory=list)
    verdict: str = ''
    reason: str = ''
    evaluation: PatentEvaluation = Field(default_factory=PatentEvaluation)


class IndustrialResult(AgentResultBase):
    news: list[NewsResult] = Field(default_factory=list)
    patents: list[PatentResult] = Field(default_factory=list)
    overall_level: ConfidenceLevel = 'LOW'
    mrl_score: int = 1
    mrl_estimate: str = 'MRL 1~3'
    mrl_rationale: str = ''


class RegulatoryResult(AgentResultBase):
    verdict: Literal['해당', '미해당', '불명확'] = '불명확'
    confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    evidences: list[RegulatoryEvidenceItem] = Field(default_factory=list)
    applicable_regulations: list[str] = Field(default_factory=list)
    incentives: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    requires_expert_review: bool = True
    source_urls: list[str] = Field(default_factory=list)
    cri_score: int = 1
    cri_estimate: str = 'CRI 1'
    cri_rationale: str = ''
    evidence_summary: str = ''
    reason: Optional[str] = None
    extracted_law_candidates: list[str] = Field(default_factory=list)
    pipeline_notes: list[str] = Field(default_factory=list)
    documents_for_validation: list[SelectedRegulatoryDocument] = Field(default_factory=list)

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


class CrossValidationResult(AgentResultBase):
    results: list[ClaimJudgement] = Field(default_factory=list)
    overall_verdict: str = '판단 보류'
    overall_confidence: ConfidenceLevel = 'LOW'
    scientific_confidence: ConfidenceLevel = 'LOW'
    industrial_confidence: ConfidenceLevel = 'LOW'
    regulatory_confidence: ConfidenceLevel = 'LOW'
    conflicts: list[str] = Field(default_factory=list)
    performance_gaps: list[PerformanceGapResult] = Field(default_factory=list)
    regulatory_conflicts: list[RegulatoryConflictResult] = Field(default_factory=list)
    fake_claims_detected: list[Claim] = Field(default_factory=list)


class ClaimVerificationResult(BaseModel):
    claim: Claim
    credibility: ConfidenceLevel = 'LOW'
    verdict: str = '판단 보류'
    flags: list[str] = Field(default_factory=list)
    trl: str = 'TRL 1~3'
    mrl: str = 'MRL 1~3'
    cri: str = 'CRI 1~3'


ScientificAgentOutput = ScientificResult
IndustrialAgentOutput = IndustrialResult
RegulatoryAgentOutput = RegulatoryResult
CrossValidatorOutput = CrossValidationResult
