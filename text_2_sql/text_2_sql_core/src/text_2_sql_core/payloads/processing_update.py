# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ProcessingUpdateHeader(BaseModel):
    timestamp: datetime = Field(
        ...,
        description="Timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )


class ProcessingUpdateBody(BaseModel):
    title: str | None = Field(default="Processing...")
    message: str | None = Field(default="Processing...")


class ProcessingUpdate(BaseModel):
    header: ProcessingUpdateHeader | None = Field(
        default_factory=ProcessingUpdateHeader
    )
    processing_update: ProcessingUpdateBody
