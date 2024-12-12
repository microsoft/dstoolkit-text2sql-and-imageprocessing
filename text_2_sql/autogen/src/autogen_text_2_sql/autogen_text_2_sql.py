# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
    SourceMatchTermination,
)
from autogen_agentchat.teams import SelectorGroupChat
from autogen_text_2_sql.creators.llm_model_creator import LLMModelCreator
from autogen_text_2_sql.creators.llm_agent_creator import LLMAgentCreator
import logging
from autogen_text_2_sql.custom_agents.sql_query_cache_agent import SqlQueryCacheAgent
from autogen_text_2_sql.custom_agents.sql_schema_selection_agent import (
    SqlSchemaSelectionAgent,
)
from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.base import Response
import json
import os
import asyncio
from datetime import datetime

class EmptyResponseUserProxyAgent(UserProxyAgent):
    """UserProxyAgent that automatically responds with empty messages."""
    def __init__(self, name):
        super().__init__(name=name)
        self._has_responded = False

    async def on_messages_stream(self, messages, sender=None, config=None):
        """Auto-respond with empty message and return Response object."""
        message = TextMessage(content="", source=self.name)
        if not self._has_responded:
            self._has_responded = True
            yield message
        yield Response(chat_message=message)

class AutoGenText2Sql:
    def __init__(self, engine_specific_rules: str, **kwargs: dict):
        self.use_query_cache = False
        self.pre_run_query_cache = False

        self.target_engine = os.environ["Text2Sql__DatabaseEngine"].upper()
        self.engine_specific_rules = engine_specific_rules

        self.kwargs = kwargs

        self.set_mode()

    def set_mode(self):
        """Set the mode of the plugin based on the environment variables."""
        self.use_query_cache = (
            os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true"
        )

        self.pre_run_query_cache = (
            os.environ.get("Text2Sql__PreRunQueryCache", "False").lower() == "true"
        )

        self.use_column_value_store = (
            os.environ.get("Text2Sql__UseColumnValueStore", "False").lower() == "true"
        )

    def get_all_agents(self):
        """Get all agents for the complete flow."""
        # Get current datetime for the Query Rewrite Agent
        current_datetime = datetime.now()
        
        QUERY_REWRITE_AGENT = LLMAgentCreator.create(
            "query_rewrite_agent",
            current_datetime=current_datetime
        )
        
        SQL_QUERY_GENERATION_AGENT = LLMAgentCreator.create(
            "sql_query_generation_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )
        
        SQL_SCHEMA_SELECTION_AGENT = SqlSchemaSelectionAgent(
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )
        
        SQL_QUERY_CORRECTION_AGENT = LLMAgentCreator.create(
            "sql_query_correction_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )
        
        SQL_DISAMBIGUATION_AGENT = LLMAgentCreator.create(
            "sql_disambiguation_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )
        
        ANSWER_AGENT = LLMAgentCreator.create("answer_agent")
        
        # Auto-responding UserProxyAgent
        USER_PROXY = EmptyResponseUserProxyAgent(
            name="user_proxy"
        )

        agents = [
            USER_PROXY,
            QUERY_REWRITE_AGENT,
            SQL_QUERY_GENERATION_AGENT,
            SQL_SCHEMA_SELECTION_AGENT,
            SQL_QUERY_CORRECTION_AGENT,
            SQL_DISAMBIGUATION_AGENT,
            ANSWER_AGENT,
        ]

        if self.use_query_cache:
            SQL_QUERY_CACHE_AGENT = SqlQueryCacheAgent()
            agents.append(SQL_QUERY_CACHE_AGENT)

        return agents

    @property
    def termination_condition(self):
        """Define the termination condition for the chat."""
        termination = (
            TextMentionTermination("TERMINATE")
            | MaxMessageTermination(20)
            | SourceMatchTermination(["answer_agent"])
        )
        return termination

    @staticmethod
    def unified_selector(messages):
        """Unified selector for the complete flow."""
        logging.info("Messages: %s", messages)
        decision = None

        # If this is the first message, start with query_rewrite_agent
        if len(messages) == 1:
            return "query_rewrite_agent"

        # Handle transition after query rewriting
        if messages[-1].source == "query_rewrite_agent":
            # Keep the array structure but process sequentially
            if os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true":
                decision = "sql_query_cache_agent"
            else:
                decision = "sql_schema_selection_agent"
        # Handle subsequent agent transitions
        elif messages[-1].source == "sql_query_cache_agent":
            try:
                cache_result = json.loads(messages[-1].content)
                if cache_result.get("cached_questions_and_schemas") is not None:
                    if cache_result.get("contains_pre_run_results"):
                        decision = "sql_query_correction_agent"
                    else:
                        decision = "sql_query_generation_agent"
                else:
                    decision = "sql_schema_selection_agent"
            except json.JSONDecodeError:
                decision = "sql_schema_selection_agent"
        elif messages[-1].source == "sql_schema_selection_agent":
            decision = "sql_disambiguation_agent"
        elif messages[-1].source == "sql_disambiguation_agent":
            decision = "sql_query_generation_agent"
        elif messages[-1].source == "sql_query_generation_agent":
            decision = "sql_query_correction_agent"
        elif messages[-1].source == "sql_query_correction_agent":
            if messages[-1].content == "VALIDATED":
                decision = "answer_agent"
            else:
                decision = "sql_query_correction_agent"
        elif messages[-1].source == "answer_agent":
            return "user_proxy"  # Let user_proxy send TERMINATE

        logging.info("Decision: %s", decision)
        return decision

    @property
    def agentic_flow(self):
        """Create the unified flow for the complete process."""
        flow = SelectorGroupChat(
            self.get_all_agents(),
            allow_repeated_speaker=False,
            model_client=LLMModelCreator.get_model("4o-mini"),
            termination_condition=self.termination_condition,
            selector_func=AutoGenText2Sql.unified_selector,
        )
        return flow

    async def process_question(self, task: str):
        """Process the complete question through the unified system."""
        result = await self.agentic_flow.run_stream(task=task)
        return result
