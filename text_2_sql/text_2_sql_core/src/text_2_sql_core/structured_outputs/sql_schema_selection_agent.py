# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel


class SQLSchemaSelectionAgentOutput(BaseModel):
    entities: list[list[str]]
    filter_conditions: list[str]
