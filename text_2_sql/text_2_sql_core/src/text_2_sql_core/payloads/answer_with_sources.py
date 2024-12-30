from pydantic import BaseModel, Field


class Source(BaseModel):
    sql_query: str
    sql_rows: list[dict]
    markdown_table: str


class AnswerWithSources(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
