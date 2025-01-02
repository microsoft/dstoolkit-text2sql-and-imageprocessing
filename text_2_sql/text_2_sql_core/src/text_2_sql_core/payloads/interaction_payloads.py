# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, RootModel, Field, model_validator
from enum import StrEnum

from typing import Literal
from datetime import datetime, timezone


class PayloadBase(BaseModel):
    prompt_tokens: int | None = Field(default=None)
    completion_tokens: int | None = Field(default=None)
    timestamp: datetime = Field(
        ...,
        description="Timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )


class PayloadSource(StrEnum):
    USER = "user"
    AGENT = "agent"


class PayloadType(StrEnum):
    ANSWER_WITH_SOURCES = "answer_with_sources"
    DISAMBIGUATION_REQUEST = "disambiguation_request"
    PROCESSING_UPDATE = "processing_update"
    QUESTION = "question"


class DismabiguationRequest(BaseModel):
    question: str
    matching_columns: list[str]
    matching_filter_values: list[str]
    other_user_choices: list[str]


class DismabiguationRequestBody(BaseModel):
    disambiguation_requests: list[DismabiguationRequest]


class DismabiguationRequestPayload(PayloadBase):
    payload_type: Literal[PayloadType.DISAMBIGUATION_REQUEST] = Field(
        default=PayloadType.DISAMBIGUATION_REQUEST
    )
    payload_source: Literal[PayloadSource.USER] = Field(default=PayloadSource.AGENT)
    body: DismabiguationRequestBody


class Source(BaseModel):
    sql_query: str
    sql_rows: list[dict]


class AnswerWithSourcesBody(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)


class AnswerWithSourcesPayload(PayloadBase):
    payload_type: Literal[PayloadType.ANSWER_WITH_SOURCES] = Field(
        default=PayloadType.ANSWER_WITH_SOURCES
    )
    payload_source: Literal[PayloadSource.USER] = Field(default=PayloadSource.AGENT)
    body: AnswerWithSourcesBody


class ProcessingUpdateBody(BaseModel):
    title: str | None = Field(default="Processing...")
    message: str | None = Field(default="Processing...")


class ProcessingUpdatePayload(PayloadBase):
    payload_type: Literal[PayloadType.PROCESSING_UPDATE] = Field(
        default=PayloadType.PROCESSING_UPDATE
    )
    payload_source: Literal[PayloadSource.USER] = Field(default=PayloadSource.AGENT)

    body: ProcessingUpdateBody


class QuestionBody(BaseModel):
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


class QuestionPayload(PayloadBase):
    payload_type: Literal[PayloadType.QUESTION] = Field(default=PayloadType.QUESTION)
    payload_source: Literal[PayloadSource.USER] = Field(default=PayloadSource.AGENT)

    body: QuestionBody


class InteractionPayload(RootModel):
    root: QuestionPayload | ProcessingUpdatePayload | DismabiguationRequestPayload | AnswerWithSourcesPayload = Field(
        ..., discriminator="payload_type"
    )
