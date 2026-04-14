from typing import Literal

from pydantic import BaseModel


class Claim(BaseModel):
    claim_id: str = ''
    claim_text: str = ''
    category: Literal['과학', '산업', '규제'] = '과학'

    # Backward-compatible fields used by the current pipeline.
    technology: str = ''
    claim: str = ''
    application: str = ''
    type: str = '성능 지표'
    status: Literal['달성', '목표'] = '달성'


class ClaimJudgement(BaseModel):
    claim_id: str = ''
    judgement: Literal['지지', '반박', '불확실'] = '불확실'
    overall_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    scientific_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    industrial_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    regulatory_confidence: Literal['HIGH', 'MED', 'LOW'] = 'LOW'
    rationale_summary: str = ''
    ref_ids: list[str] = []
