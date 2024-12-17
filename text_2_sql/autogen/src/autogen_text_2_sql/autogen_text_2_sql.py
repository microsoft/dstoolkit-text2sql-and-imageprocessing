"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
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
        self.pre_run_query_cache = False
        self.target_engine = os.environ["Text2Sql__DatabaseEngine"].upper()
        self.engine_specific_rules = engine_specific_rules
        self.kwargs = kwargs
        self.set_mode()

    def set_mode(self):
        """Set the mode of the plugin based on the environment variables."""
        self.pre_run_query_cache = (
            os.environ.get("Text2Sql__PreRunQueryCache", "True").lower() == "true"
        )
        self.use_column_value_store = (
            os.environ.get("Text2Sql__UseColumnValueStore", "True").lower() == "true"
        )

    def get_all_agents(self):
        """Get all agents for the complete flow."""
        # Get current datetime for the Query Rewrite Agent
        current_datetime = datetime.now()

        QUERY_REWRITE_AGENT = LLMAgentCreator.create(
            "query_rewrite_agent", current_datetime=current_datetime
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

        SQL_QUERY_CACHE_AGENT = SqlQueryCacheAgent()

        # Create User Proxy Agent
        USER_PROXY = EmptyResponseUserProxyAgent(name="user_proxy")

        agents = [
            USER_PROXY,
            QUERY_REWRITE_AGENT,
            SQL_QUERY_CACHE_AGENT,  # Cache agent is now always included
            SQL_SCHEMA_SELECTION_AGENT,
            SQL_DISAMBIGUATION_AGENT,
            SQL_QUERY_GENERATION_AGENT,
            SQL_QUERY_CORRECTION_AGENT,
        ]

        return agents

    @property
    def termination_condition(self):
        """Define the termination condition for the chat."""
        termination = (
            TextMentionTermination("TERMINATE")
            | (TextMentionTermination("answer") & TextMentionTermination("sources"))
            | MaxMessageTermination(20)
        )
        return termination

    def unified_selector(self, messages):
        """Unified selector for the complete flow."""
        logging.info("Messages: %s", messages)
        current_agent = messages[-1].source if messages else "start"
        decision = None

        # If this is the first message start with query_rewrite_agent
        if len(messages) == 1:
            decision = "query_rewrite_agent"
        # Handle transition after query rewriting
        elif current_agent == "query_rewrite_agent":
            decision = "sql_query_cache_agent"  # Always go to cache agent
        # Handle subsequent agent transitions
        elif current_agent == "sql_query_cache_agent":
            # Always go through schema selection after cache check
            decision = "sql_schema_selection_agent"
        elif current_agent == "sql_schema_selection_agent":
            decision = "sql_disambiguation_agent"
        elif current_agent == "sql_disambiguation_agent":
            decision = "sql_query_generation_agent"
        elif current_agent == "sql_query_generation_agent":
            decision = "sql_query_correction_agent"
        elif current_agent == "sql_query_correction_agent":
            try:
                correction_result = json.loads(messages[-1].content)
                if isinstance(correction_result, dict):
                    if "answer" in correction_result and "sources" in correction_result:
                        decision = "user_proxy"
                    elif "corrected_query" in correction_result:
                        if correction_result.get("executing", False):
                            decision = "sql_query_correction_agent"
                        else:
                            decision = "sql_query_generation_agent"
                    elif "error" in correction_result:
                        decision = "sql_query_generation_agent"
                elif isinstance(correction_result, list) and len(correction_result) > 0:
                    if "requested_fix" in correction_result[0]:
                        decision = "sql_query_generation_agent"

                if decision is None:
                    decision = "sql_query_generation_agent"
            except json.JSONDecodeError:
                decision = "sql_query_generation_agent"

        if decision:
            logging.info(f"Agent transition: {current_agent} -> {decision}")

        return decision

    @property
    def agentic_flow(self):
        """Create the unified flow for the complete process."""
        flow = SelectorGroupChat(
            self.get_all_agents(),
            allow_repeated_speaker=False,
            model_client=LLMModelCreator.get_model("4o-mini"),
            termination_condition=self.termination_condition,
            selector_func=self.unified_selector,
        )
        return flow

    async def process_question(self, task: str, chat_history: list[str] = None):
        """Process the complete question through the unified system."""

        logging.info("Processing question: %s", task)
        logging.info("Chat history: %s", chat_history)

        agent_input = {"user_question": task, "chat_history": {}}

        if chat_history is not None:
            # Update input
            for idx, chat in enumerate(chat_history):
                agent_input[f"chat_{idx}"] = chat

        result = await self.agentic_flow.run_stream(task=json.dumps(agent_input))
        return result
