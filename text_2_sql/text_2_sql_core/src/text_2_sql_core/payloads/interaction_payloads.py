# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, RootModel, Field, model_validator
from enum import StrEnum

from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4


class PayloadSource(StrEnum):
    USER = "user"
    AGENT = "agent"


class PayloadType(StrEnum):
    ANSWER_WITH_SOURCES = "answer_with_sources"
    DISAMBIGUATION_REQUESTS = "disambiguation_requests"
    PROCESSING_UPDATE = "processing_update"
    USER_INPUT = "user_input"


class PayloadBase(BaseModel):
    prompt_tokens: int | None = Field(
        None, description="Number of tokens in the prompt", alias="promptTokens"
    )
    completion_tokens: int | None = Field(
        None, description="Number of tokens in the completion", alias="completionTokens"
    )
    message_id: str = Field(
        ..., default_factory=lambda: str(uuid4()), alias="messageId"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC",
    )
    payload_type: PayloadType = Field(..., alias="payloadType")
    payload_source: PayloadSource = Field(..., alias="payloadSource")


class DismabiguationRequestsPayload(PayloadBase):
    class Body(BaseModel):
        class DismabiguationRequest(BaseModel):
            agent_question: str | None = Field(..., alias="agentQuestion")
            user_choices: list[str] | None = Field(default=None, alias="userChoices")

        disambiguation_requests: list[DismabiguationRequest] = Field(
            alias="disambiguationRequests"
        )

    payload_type: Literal[PayloadType.DISAMBIGUATION_REQUESTS] = Field(
        PayloadType.DISAMBIGUATION_REQUESTS, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.AGENT] = Field(
        default=PayloadSource.AGENT, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class AnswerWithSourcesPayload(PayloadBase):
    class Body(BaseModel):
        class Source(BaseModel):
            sql_query: str = Field(alias="sqlQuery")
            sql_rows: list[dict] = Field(default_factory=list, alias="sqlRows")

        answer: str
        decomposed_user_messages: list[str] = Field(
            default_factory=list, alias="decomposedUserMessages"
        )
        sources: list[Source] = Field(default_factory=list)

    payload_type: Literal[PayloadType.ANSWER_WITH_SOURCES] = Field(
        PayloadType.ANSWER_WITH_SOURCES, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.AGENT] = Field(
        PayloadSource.AGENT, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class ProcessingUpdatePayload(PayloadBase):
    class Body(BaseModel):
        title: str | None = "Processing..."
        message: str | None = "Processing..."

    payload_type: Literal[PayloadType.PROCESSING_UPDATE] = Field(
        PayloadType.PROCESSING_UPDATE, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.AGENT] = Field(
        PayloadSource.AGENT, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class UserInputPayload(PayloadBase):
    class Body(BaseModel):
        user_message: str = Field(..., alias="userMessage")
        injected_parameters: dict = Field(
            default_factory=dict, alias="injectedParameters"
        )

        @model_validator(mode="before")
        def add_defaults(cls, values):
            defaults = {
                "date": datetime.now().strftime("%d/%m/%Y"),
                "time": datetime.now().strftime("%H:%M:%S"),
                "datetime": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
                "unix_timestamp": int(datetime.now().timestamp()),
            }
            injected = values.get("injected_parameters", {})
            values["injected_parameters"] = {**defaults, **injected}
            return values

    payload_type: Literal[PayloadType.USER_INPUT] = Field(
        PayloadType.USER_INPUT, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.USER] = Field(
        PayloadSource.USER, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class InteractionPayload(RootModel):
    root: UserInputPayload | ProcessingUpdatePayload | DismabiguationRequestsPayload | AnswerWithSourcesPayload = Field(
        ..., discriminator="payload_type"
    )
