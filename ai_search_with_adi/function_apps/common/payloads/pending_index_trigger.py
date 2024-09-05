from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

from common.payloads.header import Header
from common.payloads.error import Error
from common.payloads.payload import Payload


class PendingIndexTriggerBody(BaseModel):
    """Body model"""

    indexer: str = Field(..., description="The indexer to trigger")
    deal_id: Optional[int] = Field(None, description="The deal ID")
    blob_storage_url: str = Field(..., description="The URL to the blob storage")
    deal_name: Optional[str] = Field(
        None, description="The text name for the integer deal ID"
    )
    business_unit: Optional[str] = Field(None, description="The business unit")

    __config__ = ConfigDict(extra="ignore")


class PendingIndexTriggerPayload(Payload):
    """Pending Index Trigger model"""

    header: Header = Field(..., description="Header information")
    body: PendingIndexTriggerBody = Field(..., description="Body information")
    errors: List[Error] | None = Field(
        ..., description="List of errors", default_factory=list
    )

    __config__ = ConfigDict(extra="ignore")
