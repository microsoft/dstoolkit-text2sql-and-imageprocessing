# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel


class AnswerAgentWithFollowUpQuestionsAgentOutput(BaseModel):
    """The output of the answer agent with follow up questions."""

    answer: str
    follow_up_questions: list[str]
