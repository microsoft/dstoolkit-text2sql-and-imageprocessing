from autogen_agentchat.task import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from utils.models import MINI_MODEL
from utils.agent_creator import AgentCreator
from autogen_core.components.models import FunctionExecutionResult
import logging

SQL_QUERY_GENERATION_AGENT = AgentCreator.create(
    "sql_query_generation_agent",
    target_engine="Microsoft SQL Server",
    engine_specific_rules="Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error.",
)
SQL_SCHEMA_SELECTION_AGENT = AgentCreator.create("sql_schema_selection_agent")
SQL_QUERY_CORRECTION_AGENT = AgentCreator.create(
    "sql_query_correction_agent",
    target_engine="Microsoft SQL Server",
    engine_specific_rules="Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error.",
)
SQL_QUERY_CACHE_AGENT = AgentCreator.create("sql_query_cache_agent")
ANSWER_AGENT = AgentCreator.create("answer_agent")
QUESTION_DECOMPOSITION_AGENT = AgentCreator.create("question_decomposition_agent")


def text_2_sql_generator_selector_func(messages):
    logging.info("Messages: %s", messages)
    if len(messages) == 1:
        return "sql_query_cache_agent"

    elif (
        messages[-1].source == "sql_query_cache_agent"
        and isinstance(messages[-1].content, FunctionExecutionResult)
        and messages[-1].content.content is not None
    ):
        return "sql_query_correction_agent"

    elif messages[-1].source == "question_decomposition_agent":
        return "sql_schema_selection_agent"

    elif messages[-1].source == "sql_schema_selection_agent":
        return "sql_query_generation_agent"

    elif (
        messages[-1].source == "sql_query_correction_agent"
        and messages[-1].content == "VALIDATED"
    ):
        return "answer_agent"

    elif messages[-1].source == "sql_query_correction_agent":
        return "sql_query_correction_agent"

    return None


termination = TextMentionTermination("TERMINATE")
text_2_sql_generator = SelectorGroupChat(
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
    selector_func=text_2_sql_generator_selector_func,
)

# text_2_sql_cache_updater = SelectorGroupChat(
#     [SQL_QUERY_CACHE_AGENT], model_client=MINI_MODEL, termination_condition=termination
# )
