from typing import Literal, Optional
from pydantic import BaseModel, Field
from .claim import Claim


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


class PaperResult(BaseModel):
    title: str
    authors: list[str] = []
    year: int = 0
    journal: str = ''
    url: str = ''
    pdf_url: str = ''
    grade_score: float = 0.0
    grade_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    citation_count: int = 0
    abstract: str = ''
    semantic_scholar_id: str = ''
    openalex_id: str = ''
    arxiv_id: str = ''
    doi: str = ''
    # Evidence pack (초록·메타 기반; 교차검증·Report용 서술)
    summary: str = ''
    excerpt: str = ''
    key_point: str = ''
    conditions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_note: str = ''


class GradeDimensionScores(BaseModel):
    """설계 §7.1 GRADE 가중치에 맞춘 자동화 스켈레톤 (0~1 구간 점수)."""

    study_design: float = Field(0.0, description='연구 설계 수준')
    bias_risk: float = Field(0.0, description='편향 위험 (높을수록 양호)')
    consistency_hint: float = Field(0.0, description='인용·일관성 힌트 (OpenAlex 등)')
    directness: float = Field(0.0, description='실제 적용 조건과의 근접도 (휴리스틱)')
    precision_hint: float = Field(0.0, description='표본·인용 규모 힌트')
    venue_authority: float = Field(0.0, description='저널·출처 권위 휴리스틱')
    weighted_total: float = Field(0.0, description='가중 합산')


class ScientificAgentOutput(BaseModel):
    papers: list[PaperResult] = []
    overall_grade: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    trl_estimate: str = 'TRL 1~3'
    summary: str = ''
    error: Optional[str] = None
    grade_breakdown: Optional[GradeDimensionScores] = None
    search_sources: list[str] = Field(default_factory=list)


class NewsResult(BaseModel):
    title: str
    provider: str = ''
    published_at: str = ''
    url: str = ''
    craap_score: float = 0.0
    craap_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    summary: str = ''
    excerpt: str = ''
    flags: list[str] = Field(default_factory=list)


class PatentResult(BaseModel):
    title: str
    applicant: str = ''
    application_date: str = ''
    status: Literal['등록', '심사중', '출원'] = '출원'
    is_core_tech: bool = False
    url: str = ''
    summary: str = ''
    key_point: str = ''
    core_level: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    flags: list[str] = Field(default_factory=list)


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
    evidence_summary: str = Field(
        default='',
        description='교차검증·Report용 근거 팩 서술(수집·판단 요약)',
    )
    error: Optional[str] = None
    # 파이프라인(Tavily → 법령 추출 → 포털 → LLM) 보강 필드
    reason: Optional[str] = None
    extracted_law_candidates: list[str] = []
    pipeline_notes: list[str] = []
    documents_for_validation: list[SelectedRegulatoryDocument] = Field(default_factory=list)


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
    papers_for_validation: list[SelectedPaperDocument] = Field(default_factory=list)
    regulations_for_validation: list[SelectedRegulatoryDocument] = Field(default_factory=list)
