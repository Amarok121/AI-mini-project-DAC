from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    claim_id: str = ''
    claim_text: str = ''
    category: Literal['과학', '산업', '규제'] = '과학'

    # Backward-compatible fields used by the current pipeline and newer agents.
    technology: str = Field(default='', max_length=500, description='기술·제품 짧은 라벨')
    claim: str = Field(default='', max_length=2000, description='검증 가능한 사실 주장')
    application: str = Field(default='', max_length=1000, description='적용 맥락')
    type: str = Field(default='성능 지표', max_length=100, description='성능 지표·경제성·규제 등')
    status: Literal['달성', '목표'] = Field(default='달성', description='달성 vs 목표/계획')


class ClaimJudgement(BaseModel):
    claim_id: str = ''
    judgement: Literal['지지', '반박', '불확실'] = '불확실'
    overall_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    scientific_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    industrial_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    regulatory_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    rationale_summary: str = ''
    ref_ids: list[str] = Field(default_factory=list)
