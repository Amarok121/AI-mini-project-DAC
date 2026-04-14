from typing import Literal

from pydantic import BaseModel, ConfigDict


SourceType = Literal['paper', 'news', 'patent', 'regulation', 'internal_doc']


class SourceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ref_id: int = 0
    title: str = ''
    authors: list[str] = []
    year: int | None = None
    source_type: SourceType = 'paper'
    url: str | None = None
    publisher: str | None = None
    raw_text: str | None = None
    apa7_citation: str | None = None
