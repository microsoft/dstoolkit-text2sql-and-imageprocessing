from pydantic import BaseModel
from text_2_sql_core.payloads.answer_with_sources import AnswerWithSources


class ChatHistoryItem(BaseModel):
    """Chat history item with user message and agent response."""

    user_query: str
    agent_response: AnswerWithSources
