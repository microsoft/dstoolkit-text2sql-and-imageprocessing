# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
)
from autogen_agentchat.teams import SelectorGroupChat
from autogen_text_2_sql.creators.llm_model_creator import LLMModelCreator
from autogen_text_2_sql.creators.llm_agent_creator import LLMAgentCreator
import logging
from autogen_text_2_sql.custom_agents.sql_query_cache_agent import (
    SqlQueryCacheAgent,
)
from autogen_text_2_sql.custom_agents.sql_schema_selection_agent import (
    SqlSchemaSelectionAgent,
)
from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.base import Response
import json
import os


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


class InnerAutoGenText2Sql:
    def __init__(self, **kwargs: dict):
        self.pre_run_query_cache = False
        self.target_engine = os.environ["Text2Sql__DatabaseEngine"].upper()
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
        self.use_query_cache = (
            os.environ.get("Text2Sql__UseQueryCache", "True").lower() == "true"
        )

        # Set the row limit
        self.kwargs["row_limit"] = int(os.environ.get("Text2Sql__RowLimit", 100))

    def get_all_agents(self):
        """Get all agents for the complete flow."""
        # If relationship_paths not provided, use a generic template
        if "relationship_paths" not in self.kwargs:
            self.kwargs[
                "relationship_paths"
            ] = """
                Common relationship paths to consider:
                - Transaction → Related Dimensions (for basic analysis)
                - Geographic → Location hierarchies (for geographic analysis)
                - Temporal → Date hierarchies (for time-based analysis)
                - Entity → Attributes (for entity-specific analysis)
            """

        sql_schema_selection_agent = SqlSchemaSelectionAgent(
            target_engine=self.target_engine,
            **self.kwargs,
        )

        sql_query_correction_agent = LLMAgentCreator.create(
            "sql_query_correction_agent",
            target_engine=self.target_engine,
            **self.kwargs,
        )

        disambiguation_and_sql_query_generation_agent = LLMAgentCreator.create(
            "disambiguation_and_sql_query_generation_agent",
            target_engine=self.target_engine,
            **self.kwargs,
        )
        agents = [
            sql_schema_selection_agent,
            sql_query_correction_agent,
            disambiguation_and_sql_query_generation_agent,
        ]

        if self.use_query_cache:
            query_cache_agent = SqlQueryCacheAgent()
            agents.append(query_cache_agent)

        return agents

    @property
    def termination_condition(self):
        """Define the termination condition for the chat."""
        termination = (
            TextMentionTermination("TERMINATE")
            | MaxMessageTermination(10)
            | TextMentionTermination("disambiguation_request")
        )
        return termination

    def unified_selector(self, messages):
        """Unified selector for the complete flow."""
        logging.info("Messages: %s", messages)
        current_agent = messages[-1].source if messages else "user"
        decision = None

        if current_agent == "user":
            decision = (
                "sql_query_cache_agent"
                if self.use_query_cache
                else "sql_schema_selection_agent"
            )
        # Handle subsequent agent transitions
        elif current_agent == "sql_query_cache_agent":
            # Always go through schema selection after cache check
            decision = "sql_schema_selection_agent"
        elif current_agent == "sql_schema_selection_agent":
            decision = "disambiguation_and_sql_query_generation_agent"
        elif current_agent == "disambiguation_and_sql_query_generation_agent":
            decision = "sql_query_correction_agent"
        elif current_agent == "sql_query_correction_agent":
            decision = "sql_query_correction_agent"

        if decision:
            logging.info(f"Agent transition: {current_agent} -> {decision}")
        else:
            logging.info(f"No agent transition defined from {current_agent}")

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

    def process_user_message(
        self,
        user_message: str,
        injected_parameters: dict = None,
        database_results: dict = None,
    ):
        """Process the complete question through the unified system.

        Args:
        ----
            task (str): The user input to process.
            injected_parameters (dict, optional): Parameters to pass to agents. Defaults to None.

        Returns:
        -------
            dict: The response from the system.
        """
        logging.info("Processing question: %s", user_message)

        agent_input = {
            "user_message": user_message,
            "injected_parameters": injected_parameters,
        }

        if database_results:
            agent_input["database_results"] = database_results

        return self.agentic_flow.run_stream(task=json.dumps(agent_input))
