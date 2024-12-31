# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, RootModel, Field, model_validator
from enum import StrEnum

from typing import Literal
from datetime import datetime, timezone


class AgentResponseHeader(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    timestamp: datetime = Field(
        ...,
        description="Timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )


class AgentResponseType(StrEnum):
    ANSWER_WITH_SOURCES = "answer_with_sources"
    DISAMBIGUATION = "disambiguation"


class DismabiguationRequest(BaseModel):
    question: str
    matching_columns: list[str]
    matching_filter_values: list[str]
    other_user_choices: list[str]


class DismabiguationRequests(BaseModel):
    response_type: Literal[AgentResponseType.DISAMBIGUATION] = Field(
        default=AgentResponseType.DISAMBIGUATION
    )
    requests: list[DismabiguationRequest]


class Source(BaseModel):
    sql_query: str
    sql_rows: list[dict]


class AnswerWithSources(BaseModel):
    response_type: Literal[AgentResponseType.ANSWER_WITH_SOURCES] = Field(
        default=AgentResponseType.ANSWER_WITH_SOURCES
    )
    answer: str
    sources: list[Source] = Field(default_factory=list)


class AgentResponseBody(RootModel):
    root: DismabiguationRequests | AnswerWithSources = Field(
        ..., discriminator="response_type"
    )


class AgentRequestBody(BaseModel):
    question: str
    injected_parameters: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    def add_defaults_to_injected_parameters(cls, values):
        if "injected_parameters" not in values:
            values["injected_parameters"] = {}

        if "date" not in values["injected_parameters"]:
            values["injected_parameters"]["date"] = datetime.now().strftime("%d/%m/%Y")

        if "time" not in values["injected_parameters"]:
            values["injected_parameters"]["time"] = datetime.now().strftime("%H:%M:%S")

        if "datetime" not in values["injected_parameters"]:
            values["injected_parameters"]["datetime"] = datetime.now().strftime(
                "%d/%m/%Y, %H:%M:%S"
            )

        if "unix_timestamp" not in values["injected_parameters"]:
            values["injected_parameters"]["unix_timestamp"] = int(
                datetime.now().timestamp()
            )

        return values


class AgentResponse(BaseModel):
    header: AgentResponseHeader | None = Field(default=None)
    request: AgentRequestBody
    response: AgentResponseBody
