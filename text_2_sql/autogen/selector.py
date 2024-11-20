from autogen_agentchat.task import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from utils.models import MINI_MODEL
from utils.agent_creator import AgentCreator

SQL_QUERY_GENERATION_AGENT = AgentCreator.create("sql_query_generation_agent")
SQL_SCHEMA_SELECTION_AGENT = AgentCreator.create("sql_schema_selection_agent")
SQL_QUERY_CORRECTION_AGENT = AgentCreator.create("sql_query_correction_agent")
SQL_QUERY_CACHE_AGENT = AgentCreator.create("sql_query_cache_agent")
ANSWER_AGENT = AgentCreator.create("answer_agent")
QUESTION_DECOMPOSITION_AGENT = AgentCreator.create("question_decomposition_agent")

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
