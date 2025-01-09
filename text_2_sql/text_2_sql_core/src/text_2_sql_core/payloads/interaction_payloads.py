# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, RootModel, Field, model_validator
from enum import StrEnum

from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4


class PayloadBase(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    message_id: str = Field(..., default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC",
    )
    payload_type: str
    payload_source: str


class PayloadSource(StrEnum):
    USER = "user"
    AGENT = "agent"


class PayloadType(StrEnum):
    ANSWER_WITH_SOURCES = "answer_with_sources"
    DISAMBIGUATION_REQUEST = "disambiguation_request"
    PROCESSING_UPDATE = "processing_update"
    USER_INPUT = "user_input"


class Choice(BaseModel):
    value: str
    display: str


class DismabiguationRequestsPayload(PayloadBase):
    class Body(BaseModel):
        class DismabiguationRequest(BaseModel):
            question: str
            choices: list[Choice] | None = Field(default=None)

        disambiguation_requests: list[DismabiguationRequest]

    payload_type: Literal[
        PayloadType.DISAMBIGUATION_REQUEST
    ] = PayloadType.DISAMBIGUATION_REQUEST
    payload_source: Literal[PayloadSource.AGENT] = PayloadSource.AGENT
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


request = DismabiguationRequestsPayload(
    disambiguation_requests=[
        {
            "question": "Which of the following do you mean?",
            "choices": [
                {
                    "value": "product_name - Road Bike",
                    "display": "Road Bike",
                },
                {
                    "value": "product_name - Mountain Bike",
                    "display": "Mountain Bike",
                },
            ],
        },
        {
            "question": "Do you mean total sales by volume or number of customers?",
            "choices": [
                {
                    "value": "total_sales - volume",
                    "display": "Total Sales by Volume",
                },
                {
                    "value": "total_sales - customers",
                    "display": "Number of Customers",
                },
            ],
        },
    ]
)

print(request.model_dump_json())


class AnswerWithSourcesPayload(PayloadBase):
    class Body(BaseModel):
        class Source(BaseModel):
            sql_query: str
            sql_rows: list[dict]

        answer: str
        sub_questions: list[str] = Field(default_factory=list)
        sources: list[Source] = Field(default_factory=list)

    payload_type: Literal[
        PayloadType.ANSWER_WITH_SOURCES
    ] = PayloadType.ANSWER_WITH_SOURCES
    payload_source: Literal[PayloadSource.AGENT] = PayloadSource.AGENT
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class ProcessingUpdatePayload(PayloadBase):
    class Body(BaseModel):
        title: str | None = "Processing..."
        message: str | None = "Processing..."

    payload_type: Literal[PayloadType.PROCESSING_UPDATE] = PayloadType.PROCESSING_UPDATE
    payload_source: Literal[PayloadSource.AGENT] = PayloadSource.AGENT
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class UserInputPayload(PayloadBase):
    class Body(BaseModel):
        question: str
        injected_parameters: dict = Field(default_factory=dict)

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

    payload_type: Literal[PayloadType.USER_INPUT] = PayloadType.USER_INPUT
    payload_source: Literal[PayloadSource.USER] = PayloadSource.USER
    body: Body | None = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.body = self.Body(**kwargs)


class InteractionPayload(RootModel):
    root: UserInputPayload | ProcessingUpdatePayload | DismabiguationRequestsPayload | AnswerWithSourcesPayload = Field(
        ..., discriminator="payload_type"
    )
