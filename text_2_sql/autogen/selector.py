from autogen_agentchat.task import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from utils.models import MINI_MODEL

from sql_tools_and_agents import (
    SQL_QUERY_GENERATION_AGENT,
    SQL_SCHEMA_SELECTION_AGENT,
    SQL_QUERY_CORRECTION_AGENT,
    SQL_QUERY_CACHE_AGENT,
)
from qna_agents import ANSWER_AGENT, QUESTION_DECOMPOSITION_AGENT

termination = TextMentionTermination("TERMINATE")
SELECTOR = SelectorGroupChat(
    [
        SQL_QUERY_GENERATION_AGENT,
        SQL_SCHEMA_SELECTION_AGENT,
        SQL_QUERY_CORRECTION_AGENT,
        SQL_QUERY_CACHE_AGENT,
        ANSWER_AGENT,
        QUESTION_DECOMPOSITION_AGENT,
    ],
    model_client=MINI_MODEL,
    termination_condition=termination,
)
