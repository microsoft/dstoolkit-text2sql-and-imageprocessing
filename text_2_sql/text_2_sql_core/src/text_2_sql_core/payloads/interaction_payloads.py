# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, RootModel, Field, model_validator, ConfigDict
from enum import StrEnum

from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4

DEFAULT_INJECTED_PARAMETERS = {
    "date": datetime.now().strftime("%d/%m/%Y"),
    "time": datetime.now().strftime("%H:%M:%S"),
    "datetime": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
    "unix_timestamp": int(datetime.now().timestamp()),
}


class PayloadSource(StrEnum):
    """Payload source enum."""

    USER = "user"
    ASSISTANT = "assistant"


class PayloadType(StrEnum):
    """Payload type enum."""

    ANSWER_WITH_SOURCES = "answer_with_sources"
    DISAMBIGUATION_REQUESTS = "disambiguation_requests"
    PROCESSING_UPDATE = "processing_update"
    USER_MESSAGE = "user_message"


class PayloadAndBodyBase(BaseModel):
    """Base class for payloads and bodies."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PayloadBase(PayloadAndBodyBase):
    """Base class for payloads."""

    message_id: str = Field(
        ..., default_factory=lambda: str(uuid4()), alias="messageId"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC",
    )
    payload_type: PayloadType = Field(..., alias="payloadType")
    payload_source: PayloadSource = Field(..., alias="payloadSource")

    body: PayloadAndBodyBase | None = Field(default=None)


class DismabiguationRequestsPayload(PayloadAndBodyBase):
    """Disambiguation requests payload. Handles requests for the end user to response to"""

    class Body(PayloadAndBodyBase):
        class DismabiguationRequest(PayloadAndBodyBase):
            assistant_question: str | None = Field(..., alias="assistantQuestion")
            user_choices: list[str] | None = Field(default=None, alias="userChoices")

        disambiguation_requests: list[DismabiguationRequest] | None = Field(
            default_factory=list, alias="disambiguationRequests"
        )
        steps: list[list[str]] = Field(default_factory=list, alias="Steps")

    payload_type: Literal[PayloadType.DISAMBIGUATION_REQUESTS] = Field(
        PayloadType.DISAMBIGUATION_REQUESTS, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.ASSISTANT] = Field(
        default=PayloadSource.ASSISTANT, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        """Custom init method to pass kwargs to the body."""
        super().__init__(**kwargs)

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class AnswerWithSourcesPayload(PayloadAndBodyBase):
    """Answer with sources payload. Handles the answer and sources for the answer. The follow up suggestion property is optional and may be used to provide the user with a follow up suggestion."""

    class Body(PayloadAndBodyBase):
        class Source(PayloadAndBodyBase):
            sql_query: str = Field(alias="sqlQuery")
            sql_rows: list[dict] = Field(default_factory=list, alias="sqlRows")

        answer: str
        steps: list[list[str]] = Field(default_factory=list, alias="Steps")
        sources: list[Source] = Field(default_factory=list)
        follow_up_suggestions: list[str] | None = Field(
            default=None, alias="followUpSuggestions"
        )

    payload_type: Literal[PayloadType.ANSWER_WITH_SOURCES] = Field(
        PayloadType.ANSWER_WITH_SOURCES, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.ASSISTANT] = Field(
        PayloadSource.ASSISTANT, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        """Custom init method to pass kwargs to the body."""
        super().__init__(**kwargs)

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class ProcessingUpdatePayload(PayloadAndBodyBase):
    """Processing update payload. Handles updates to the user on the processing status."""

    class Body(PayloadAndBodyBase):
        title: str | None = "Processing..."
        message: str | None = "Processing..."

    payload_type: Literal[PayloadType.PROCESSING_UPDATE] = Field(
        PayloadType.PROCESSING_UPDATE, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.ASSISTANT] = Field(
        PayloadSource.ASSISTANT, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        """Custom init method to pass kwargs to the body."""
        super().__init__(**kwargs)

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class UserMessagePayload(PayloadAndBodyBase):
    """User message payload. Handles the user message and injected parameters."""

    class Body(PayloadAndBodyBase):
        user_message: str = Field(..., alias="userMessage")
        injected_parameters: dict = Field(
            default_factory=dict, alias="injectedParameters"
        )

        @model_validator(mode="before")
        def add_defaults(cls, values):
            injected = values.get("injected_parameters", None)

            if injected is None:
                injected_by_alias = values.get("injectedParameters", {})
            else:
                injected_by_alias = injected
                del values["injected_parameters"]

            values["injectedParameters"] = {
                **DEFAULT_INJECTED_PARAMETERS,
                **injected_by_alias,
            }
            return values

    payload_type: Literal[PayloadType.USER_MESSAGE] = Field(
        PayloadType.USER_MESSAGE, alias="payloadType"
    )
    payload_source: Literal[PayloadSource.USER] = Field(
        PayloadSource.USER, alias="payloadSource"
    )
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        """Custom init method to pass kwargs to the body."""
        super().__init__(**kwargs)

        body_kwargs = kwargs.get("body", kwargs)

        self.body = self.Body(**body_kwargs)


class InteractionPayload(RootModel):
    """Interaction payload. Handles the root payload for the interaction"""

    root: UserMessagePayload | ProcessingUpdatePayload | DismabiguationRequestsPayload | AnswerWithSourcesPayload = Field(
        ..., discriminator="payload_type"
    )
