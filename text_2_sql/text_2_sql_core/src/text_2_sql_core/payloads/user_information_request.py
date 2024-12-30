from pydantic import BaseModel, RootModel, Field
from enum import StrEnum
from typing import Literal


class RequestType(StrEnum):
    DISAMBIGUATION = "disambiguation"
    CLARIFICATION = "clarification"


class ClarificationRequest(BaseModel):
    request_type: Literal[RequestType.CLARIFICATION]
    question: str
    other_user_choices: list[str]


class DismabiguationRequest(BaseModel):
    request_type: Literal[RequestType.DISAMBIGUATION]
    question: str
    matching_columns: list[str]
    matching_filter_values: list[str]
    other_user_choices: list[str]


class UserInformationRequest(RootModel):
    root: DismabiguationRequest = Field(..., discriminator="request_type")
