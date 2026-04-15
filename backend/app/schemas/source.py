from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


SourceType = Literal['paper', 'news', 'patent', 'regulation', 'internal_doc']


class SourceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ref_id: int = 0
    title: str = ''
    authors: list[str] = []
    year: Optional[int] = None
    source_type: SourceType = 'paper'
    url: Optional[str] = None
    publisher: Optional[str] = None
    raw_text: Optional[str] = None
    apa7_citation: Optional[str] = None
