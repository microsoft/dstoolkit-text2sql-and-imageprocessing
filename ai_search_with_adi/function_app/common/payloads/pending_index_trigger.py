# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

from common.payloads.header import Header
from common.payloads.error import Error
from common.payloads.payload import Payload


class PendingIndexTriggerBody(BaseModel):
    """Body model"""

    indexer: str = Field(..., description="The indexer to trigger")
    ## this field can be defined based on your id field
    id_field: Optional[int] = Field(None, description="The ID field")
    blob_storage_url: str = Field(..., description="The URL to the blob storage")
    ## this field can be defined based on your id field
    id_name: Optional[str] = Field(
        None, description="The text name for the integer ID field"
    )
    additional_field: Optional[str] = Field(
        None, description="Description of additional_field"
    )

    __config__ = ConfigDict(extra="ignore")


class PendingIndexTriggerPayload(Payload):
    """Pending Index Trigger model"""

    header: Header = Field(..., description="Header information")
    body: PendingIndexTriggerBody = Field(..., description="Body information")
    errors: List[Error] | None = Field(
        ..., description="List of errors", default_factory=list
    )

    __config__ = ConfigDict(extra="ignore")
