# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel


class AnswerAgentWithFollowUpQuestionsAgentOutput(BaseModel):
    answer: str
    follow_up_questions: list[str]
