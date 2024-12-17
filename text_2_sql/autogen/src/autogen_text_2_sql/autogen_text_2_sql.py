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
            os.environ.get("Text2Sql__UseQueryCache", "True").lower() == "true"
        )

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

        self.query_rewrite_agent = LLMAgentCreator.create(
            "query_rewrite_agent", current_datetime=current_datetime
        )

        self.sql_query_generation_agent = LLMAgentCreator.create(
            "sql_query_generation_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )

        self.sql_schema_selection_agent = SqlSchemaSelectionAgent(
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )

        self.sql_query_correction_agent = LLMAgentCreator.create(
            "sql_query_correction_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )

        self.sql_disambiguation_agent = LLMAgentCreator.create(
            "sql_disambiguation_agent",
            target_engine=self.target_engine,
            engine_specific_rules=self.engine_specific_rules,
            **self.kwargs,
        )

        # Auto-responding UserProxyAgent
        self.user_proxy = EmptyResponseUserProxyAgent(name="user_proxy")

        agents = [
            self.user_proxy,
            self.query_rewrite_agent,
            self.sql_query_generation_agent,
            self.sql_schema_selection_agent,
            self.sql_query_correction_agent,
            self.sql_disambiguation_agent,
        ]

        if self.use_query_cache:
            self.query_cache_agent = SqlQueryCacheAgent()
            agents.append(self.query_cache_agent)

        return agents

    @property
    def termination_condition(self):
        """Define the termination condition for the chat."""
        termination = (
            TextMentionTermination("TERMINATE")
            | (
                TextMentionTermination("answer")
                & TextMentionTermination("sources")
                & SourceMatchTermination("sql_query_correction_agent")
            )
            | MaxMessageTermination(20)
        )
        return termination

    def unified_selector(self, messages):
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

        elif messages[-1].source == "sql_query_correction_agent":
            decision = "sql_query_generation_agent"

        elif messages[-1].source == "sql_query_generation_agent":
            decision = "sql_query_correction_agent"
        elif messages[-1].source == "sql_query_correction_agent":
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
            selector_func=self.unified_selector,
        )
        return flow

    async def process_question(
        self, task: str, chat_history: list[str] = None, parameters: dict = None
    ):
        """Process the complete question through the unified system.

        Args:
        ----
            task (str): The user question to process.
            chat_history (list[str], optional): The chat history. Defaults to None.
            parameters (dict, optional): The parameters to pass to the agents. Defaults to None.

        Returns:
        -------
            dict: The response from the system.
        """

        logging.info("Processing question: %s", task)
        logging.info("Chat history: %s", chat_history)

        agent_input = {
            "user_question": task,
            "chat_history": {},
            "parameters": parameters,
        }

        if chat_history is not None:
            # Update input
            for idx, chat in enumerate(chat_history):
                agent_input[f"chat_{idx}"] = chat

        return self.agentic_flow.run_stream(task=json.dumps(agent_input))
