# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel


class UserMessageRewriteAgentOutput(BaseModel):
    """The output of the user message rewrite agent."""

    steps: list[list[str]]
    requires_sql_queries: bool
