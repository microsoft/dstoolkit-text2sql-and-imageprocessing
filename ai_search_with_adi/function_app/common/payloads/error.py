# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Error(BaseModel):
    """Error item model"""

    code: str = Field(..., description="The error code")
    message: str = Field(..., description="The error message")
    details: Optional[str] = Field(
        None, description="Detailed error information from Python"
    )
    timestamp: Optional[datetime] = Field(
        ...,
        description="Creation timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )

    __config__ = ConfigDict(extra="ignore")
