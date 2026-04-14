from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """기술 검증용 클레임. 길이·리터럴은 모델과 후처리에서 이중으로 맞춘다."""

    technology: str = Field(..., min_length=1, max_length=500, description='기술·제품 짧은 라벨')
    claim: str = Field(..., min_length=8, max_length=2000, description='검증 가능한 사실 주장')
    application: str = Field(default='', max_length=1000, description='적용 맥락')
    type: str = Field(default='일반', max_length=100, description='성능 지표·경제성·규제 등')
    status: Literal['달성', '목표'] = Field(default='목표', description='달성 vs 목표/계획')
