# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, RootModel, Field, model_validator, ConfigDict
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
    USER_MESSAGE = "user_message"


class InteractionPayloadBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PayloadBase(InteractionPayloadBase):
    message_id: str = Field(
        ..., default_factory=lambda: str(uuid4()), alias="messageId"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC",
    )
    payload_type: PayloadType = Field(..., alias="payloadType")
    payload_source: PayloadSource = Field(..., alias="payloadSource")


class DismabiguationRequestsPayload(InteractionPayloadBase):
    class Body(InteractionPayloadBase):
        class DismabiguationRequest(InteractionPayloadBase):
            agent_question: str | None = Field(..., alias="agentQuestion")
            user_choices: list[str] | None = Field(default=None, alias="userChoices")

        disambiguation_requests: list[DismabiguationRequest] | None = Field(
            default_factory=list, alias="disambiguationRequests"
        )
        decomposed_user_messages: list[list[str]] = Field(
            default_factory=list, alias="decomposedUserMessages"
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

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class AnswerWithSourcesPayload(InteractionPayloadBase):
    class Body(InteractionPayloadBase):
        class Source(InteractionPayloadBase):
            sql_query: str = Field(alias="sqlQuery")
            sql_rows: list[dict] = Field(default_factory=list, alias="sqlRows")

        answer: str
        decomposed_user_messages: list[list[str]] = Field(
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

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class ProcessingUpdatePayload(InteractionPayloadBase):
    class Body(InteractionPayloadBase):
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

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class UserMessagePayload(InteractionPayloadBase):
    class Body(InteractionPayloadBase):
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
            injected = values.get("injected_parameters", None)

            if injected is None:
                injected_by_alias = values.get("injectedParameters", {})
            else:
                injected_by_alias = injected
                del values["injected_parameters"]

            values["injectedParameters"] = {**defaults, **injected_by_alias}
            return values

    payload_type: Literal[PayloadType.USER_MESSAGE] = Field(
        PayloadType.USER_MESSAGE, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.USER] = Field(
        PayloadSource.USER, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class InteractionPayload(RootModel):
    root: UserMessagePayload | ProcessingUpdatePayload | DismabiguationRequestsPayload | AnswerWithSourcesPayload = Field(
        ..., discriminator="payload_type"
    )
