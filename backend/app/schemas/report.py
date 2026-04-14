from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .agent_result import CrossValidationResult, IndustrialResult, RegulatoryResult, ScientificResult
from .claim import Claim


class ReportInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scientific_result: ScientificResult = Field(validation_alias=AliasChoices('scientific_result', 'scientific'))
    industrial_result: IndustrialResult = Field(validation_alias=AliasChoices('industrial_result', 'industrial'))
    regulatory_result: RegulatoryResult = Field(validation_alias=AliasChoices('regulatory_result', 'regulatory'))
    cross_validation_result: CrossValidationResult = Field(
        validation_alias=AliasChoices('cross_validation_result', 'cross_validation')
    )
    original_claims: list[Claim] = Field(default_factory=list, validation_alias=AliasChoices('original_claims', 'claims'))
    company_name: str = 'SK이노베이션'
    company_context: str = ''
    company_context_section6: str = ''

    @property
    def scientific(self) -> ScientificResult:
        return self.scientific_result

    @property
    def industrial(self) -> IndustrialResult:
        return self.industrial_result

    @property
    def regulatory(self) -> RegulatoryResult:
        return self.regulatory_result

    @property
    def cross_validation(self) -> CrossValidationResult:
        return self.cross_validation_result

    @property
    def claims(self) -> list[Claim]:
        return self.original_claims


class SectionDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    section_id: str
    title: str
    content_markdown: str = Field(
        default='',
        validation_alias=AliasChoices('content_markdown', 'markdown'),
    )
    ref_ids_used: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices('ref_ids_used', 'ref_ids'),
    )
    error: str | None = None
    has_error: bool = False

    @property
    def markdown(self) -> str:
        return self.content_markdown

    @property
    def ref_ids(self) -> list[int]:
        return self.ref_ids_used


class CitationMeta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ref_id: int
    apa7_citation: str = Field(validation_alias=AliasChoices('apa7_citation', 'apa_citation'))
    raw_text: str | None = Field(default=None, validation_alias=AliasChoices('raw_text', 'snippet'))
    url: str | None = None
    source_type: str


class ScoreItem(BaseModel):
    value: int | None = None
    min: int
    max: int
    label: str
    rationale: str = ''


class ScoreSummary(BaseModel):
    trl: ScoreItem
    mrl: ScoreItem
    cri: ScoreItem


class ClaimVerdictChart(BaseModel):
    claim_id: str
    claim_text: str
    verdict: str
    confidence: float
    scientific_confidence: float | None = None
    industrial_confidence: float | None = None
    regulatory_confidence: float | None = None


class RoadmapStep(BaseModel):
    step: int
    phase: str
    trl_range: str
    mrl_range: str
    description: str


class ChartData(BaseModel):
    score_summary: ScoreSummary | None = None
    claim_verdicts: list[ClaimVerdictChart] = []
    roadmap_steps: list[RoadmapStep] = []


class ReportOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_markdown: str = Field(validation_alias=AliasChoices('report_markdown', 'markdown'))
    sections: list[SectionDraft] = Field(
        default_factory=list,
        validation_alias=AliasChoices('sections', 'section_drafts'),
    )
    citation_metadata: list[CitationMeta] = []
    chart_data: ChartData | None = None
    pdf_path: str | None = None
    error: str | None = None

    @property
    def markdown(self) -> str:
        return self.report_markdown

    @property
    def section_drafts(self) -> list[SectionDraft]:
        return self.sections
