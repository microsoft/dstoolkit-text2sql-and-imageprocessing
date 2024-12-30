from pydantic import BaseModel, Field


class Source(BaseModel):
    sql_query: str
    sql_rows: list[dict]


class AnswerWithSources(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
