# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, Field
from text_2_sql_core.payloads.agent_response import AgentResponse
from datetime import datetime, timezone


class ChatHistoryItem(BaseModel):
    """Chat history item with user message and agent response."""

    timestamp: datetime = Field(
        ...,
        description="Timestamp in UTC",
        default_factory=lambda: datetime.now(timezone.utc),
    )
    agent_response: AgentResponse
