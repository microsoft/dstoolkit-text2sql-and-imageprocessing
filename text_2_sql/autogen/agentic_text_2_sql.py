# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_agentchat.task import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import SelectorGroupChat
from llm_model_creator import LLMModelCreator
from llm_agent_creator import LLMAgentCreator
import logging
from custom_agents.sql_query_cache_agent import SqlQueryCacheAgent
import json
import os


class AgenticText2Sql:
    def __init__(self, target_engine: str, engine_specific_rules: str):
        self.use_query_cache = False
        self.pre_run_query_cache = False

        self.target_engine = target_engine
        self.engine_specific_rules = engine_specific_rules

        self.set_mode()

    def set_mode(self):
        """Set the mode of the plugin based on the environment variables."""
        self.use_query_cache = (
            os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true"
        )

        self.pre_run_query_cache = (
            os.environ.get("Text2Sql__PreRunQueryCache", "False").lower() == "true"
        )

    @property
    def agents(self):
        """Define the agents for the chat."""
        SQL_QUERY_GENERATION_AGENT = LLMAgentCreator.create(
            "sql_query_generation_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
        )
        SQL_SCHEMA_SELECTION_AGENT = LLMAgentCreator.create(
            "sql_schema_selection_agent",
            use_case="Sales data for a company that specializes in selling products online.",
        )
        SQL_QUERY_CORRECTION_AGENT = LLMAgentCreator.create(
            "sql_query_correction_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
        )

        ANSWER_AGENT = LLMAgentCreator.create("answer_agent")
        QUESTION_DECOMPOSITION_AGENT = LLMAgentCreator.create(
            "question_decomposition_agent"
        )

        agents = [
            SQL_QUERY_GENERATION_AGENT,
            SQL_SCHEMA_SELECTION_AGENT,
            SQL_QUERY_CORRECTION_AGENT,
            ANSWER_AGENT,
            QUESTION_DECOMPOSITION_AGENT,
        ]

        if self.use_query_cache:
            SQL_QUERY_CACHE_AGENT = SqlQueryCacheAgent()
            agents.append(SQL_QUERY_CACHE_AGENT)

        return agents

    @property
    def termination_condition(self):
        """Define the termination condition for the chat."""
        termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(10)
        return termination

    @staticmethod
    def selector(messages):
        logging.info("Messages: %s", messages)
        decision = None  # Initialize decision variable

        if len(messages) == 1:
            decision = "sql_query_cache_agent"

        elif (
            messages[-1].source == "sql_query_cache_agent"
            and messages[-1].content is not None
        ):
            cache_result = json.loads(messages[-1].content)
            if cache_result.get(
                "cached_questions_and_schemas"
            ) is not None and cache_result.get("contains_pre_run_results"):
                decision = "sql_query_correction_agent"
            if (
                cache_result.get("cached_questions_and_schemas") is not None
                and cache_result.get("contains_pre_run_results") is False
            ):
                decision = "sql_query_generation_agent"
            else:
                decision = "question_decomposition_agent"

        elif messages[-1].source == "question_decomposition_agent":
            decomposition_result = json.loads(messages[-1].content)

            if len(decomposition_result["entities"]) == 1:
                decision = "sql_schema_selection_agent"
            else:
                decision = "parallel_sql_flow_agent"

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

    @property
    def agentic_flow(self):
        """Run the agentic flow for the given question.

        Args:
        ----
            question (str): The question to run the agentic flow on."""
        agentic_flow = SelectorGroupChat(
            self.agents,
            allow_repeated_speaker=False,
            model_client=LLMModelCreator.get_model("4o-mini"),
            termination_condition=self.termination_condition,
            selector_func=AgenticText2Sql.selector,
        )

        return agentic_flow
