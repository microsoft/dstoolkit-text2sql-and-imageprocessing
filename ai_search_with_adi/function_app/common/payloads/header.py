# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from enum import Enum


class DataTypeEnum(Enum):
    """Type enum"""

    BUSINESS_GLOSSARY = "business_glossary"
    SUMMARY = "summary"


class TaskEnum(Enum):
    """Task enum"""

    PENDING_INDEX_COMPLETION = "pending_index_completion"
    PENDING_INDEX_TRIGGER = "pending_index_trigger"


class Header(BaseModel):
    """Header model"""

    creation_timestamp: datetime = Field(
        ...,
        description="Creation timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )
    last_processed_timestamp: datetime = Field(
        ...,
        description="Last processed timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )
    retries_remaining: int = Field(
        description="Number of retries remaining", default=10
    )
    data_type: DataTypeEnum = Field(..., description="Data type")
    task: TaskEnum = Field(..., description="Task name")

    __config__ = ConfigDict(extra="ignore")
