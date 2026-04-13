from typing import Literal
from pydantic import BaseModel


class Claim(BaseModel):
    technology: str
    claim: str
    application: str = ''
    type: str = '성능 지표'
    status: Literal['달성', '목표'] = '달성'
