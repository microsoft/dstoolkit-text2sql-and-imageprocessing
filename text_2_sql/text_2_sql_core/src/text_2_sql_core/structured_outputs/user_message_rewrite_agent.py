# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel


class UserMessageRewriteAgentOutput(BaseModel):
    decomposed_user_messages: list[list[str]]
    combination_logic: str
    query_type: str
    all_non_database_query: bool
