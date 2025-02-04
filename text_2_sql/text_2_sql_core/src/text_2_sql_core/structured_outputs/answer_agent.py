# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel


class AnswerAgentOutput(BaseModel):
    """The output of the answer agent with follow up questions."""

    answer: str
