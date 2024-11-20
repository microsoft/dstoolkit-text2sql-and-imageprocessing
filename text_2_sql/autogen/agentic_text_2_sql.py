from autogen_agentchat.task import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import SelectorGroupChat
from utils.models import MINI_MODEL
from utils.llm_agent_creator import LLMAgentCreator
import logging
from custom_agents.sql_query_cache_agent import SqlQueryCacheAgent
import json

SQL_QUERY_GENERATION_AGENT = LLMAgentCreator.create(
    "sql_query_generation_agent",
    target_engine="Microsoft SQL Server",
    engine_specific_rules="Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error.",
)
SQL_SCHEMA_SELECTION_AGENT = LLMAgentCreator.create("sql_schema_selection_agent")
SQL_QUERY_CORRECTION_AGENT = LLMAgentCreator.create(
    "sql_query_correction_agent",
    target_engine="Microsoft SQL Server",
    engine_specific_rules="Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error.",
)
SQL_QUERY_CACHE_AGENT = SqlQueryCacheAgent()
ANSWER_AGENT = LLMAgentCreator.create("answer_agent")
QUESTION_DECOMPOSITION_AGENT = LLMAgentCreator.create("question_decomposition_agent")


def text_2_sql_generator_selector_func(messages):
    logging.info("Messages: %s", messages)
    decision = None  # Initialize decision variable

    if len(messages) == 1:
        decision = "sql_query_cache_agent"

    elif (
        messages[-1].source == "sql_query_cache_agent"
        and messages[-1].content is not None
    ):
        cache_result = json.loads(messages[-1].content)
        if cache_result.get("cached_questions_and_schemas") is not None:
            decision = "sql_query_correction_agent"
        else:
            decision = "sql_schema_selection_agent"

    elif messages[-1].source == "question_decomposition_agent":
        decision = "sql_schema_selection_agent"

    elif messages[-1].source == "sql_schema_selection_agent":
        decision = "sql_query_generation_agent"

    elif (
        messages[-1].source == "sql_query_correction_agent"
        and messages[-1].content == "VALIDATED"
    ):
        decision = "answer_agent"

    elif messages[-1].source == "sql_query_correction_agent":
        decision = "sql_query_correction_agent"

    # Log the decision
    logging.info("Decision: %s", decision)

    return decision


termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(10)
text_2_sql_generator = SelectorGroupChat(
    [
        SQL_QUERY_GENERATION_AGENT,
        SQL_SCHEMA_SELECTION_AGENT,
        SQL_QUERY_CORRECTION_AGENT,
        SQL_QUERY_CACHE_AGENT,
        ANSWER_AGENT,
        QUESTION_DECOMPOSITION_AGENT,
    ],
    allow_repeated_speaker=False,
    model_client=MINI_MODEL,
    termination_condition=termination,
    selector_func=text_2_sql_generator_selector_func,
)

# text_2_sql_cache_updater = SelectorGroupChat(
#     [SQL_QUERY_CACHE_AGENT], model_client=MINI_MODEL, termination_condition=termination
# )
