# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional, List

from common.payloads.header import Header
from common.payloads.error import Error
from common.payloads.payload import Payload


class PendingIndexCompletionBody(BaseModel):
    """Body model"""

    indexer: str = Field(..., description="The indexer to trigger")
    id_field: Optional[int] = Field(None, description="The ID field")
    blob_storage_url: Optional[str] = Field(
        ..., description="The URL to the blob storage"
    )
    id_name: Optional[str] = Field(
        None, description="The text name for the integer ID field"
    )
    business_unit: Optional[str] = Field(None, description="The business unit")
    indexer_start_time: Optional[datetime] = Field(
        ...,
        description="The time the indexer was triggered successfully",
        default_factory=lambda: datetime.now(timezone.utc),
    )

    __config__ = ConfigDict(extra="ignore")


class PendingIndexCompletionPayload(Payload):
    """Pending Index Trigger model"""

    header: Header = Field(..., description="Header information")
    body: PendingIndexCompletionBody = Field(..., description="Body information")
    errors: List[Error] | None = Field(
        ..., description="List of errors", default_factory=list
    )

    __config__ = ConfigDict(extra="ignore")
