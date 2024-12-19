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
from autogen_text_2_sql.custom_agents.sql_query_cache_agent import (
    SqlQueryCacheAgent,
)
from autogen_text_2_sql.custom_agents.sql_schema_selection_agent import (
    SqlSchemaSelectionAgent,
)
from autogen_text_2_sql.custom_agents.answer_and_sources_agent import (
    AnswerAndSourcesAgent,
)
from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.base import Response, TaskResult
import json
import os
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any, List


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
        
        # Initialize all agents
        self.agents = self.get_all_agents()
        
        # Create the flow
        self._flow = None

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

        self.answer_and_sources_agent = AnswerAndSourcesAgent()

        # Auto-responding UserProxyAgent
        self.user_proxy = EmptyResponseUserProxyAgent(name="user_proxy")

        agents = [
            self.user_proxy,
            self.query_rewrite_agent,
            self.sql_query_generation_agent,
            self.sql_schema_selection_agent,
            self.sql_query_correction_agent,
            self.sql_disambiguation_agent,
            self.answer_and_sources_agent,
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
            decision = "sql_disambiguation_agent"
        elif current_agent == "sql_disambiguation_agent":
            decision = "sql_query_generation_agent"
        elif current_agent == "sql_query_generation_agent":
            decision = "sql_query_correction_agent"
        elif current_agent == "sql_query_correction_agent":
            try:
                correction_result = json.loads(messages[-1].content)
                if isinstance(correction_result, dict):
                    if "error" in correction_result:
                        # Let error response terminate naturally
                        return None
                    elif "answer" in correction_result and "sources" in correction_result:
                        # Pass successful results to answer_and_sources_agent
                        decision = "answer_and_sources_agent"
                    elif "corrected_query" in correction_result:
                        if correction_result.get("executing", False):
                            decision = "sql_query_correction_agent"
                        else:
                            decision = "sql_query_generation_agent"
                elif isinstance(correction_result, list) and len(correction_result) > 0:
                    if "requested_fix" in correction_result[0]:
                        decision = "sql_query_generation_agent"

                if decision is None:
                    decision = "sql_query_generation_agent"
            except json.JSONDecodeError:
                decision = "sql_query_generation_agent"
        elif current_agent == "answer_and_sources_agent":
            decision = "user_proxy"  # Let user_proxy send TERMINATE

        if decision:
            logging.info(f"Agent transition: {current_agent} -> {decision}")

        return decision

    @property
    def agentic_flow(self):
        """Create the unified flow for the complete process."""
        if self._flow is None:
            self._flow = SelectorGroupChat(
                self.agents,
                allow_repeated_speaker=False,
                model_client=LLMModelCreator.get_model("4o-mini"),
                termination_condition=self.termination_condition,
                selector_func=self.unified_selector,
            )
        return self._flow

    async def process_sub_query(self, sub_query: dict, parameters: dict = None) -> AsyncGenerator[Any, None]:
        """Process a single sub-query through the agent flow."""
        agent_input = {
            "user_question": sub_query["query"],
            "chat_history": {},
            "parameters": parameters,
            "sub_query_id": sub_query.get("id"),
        }
        
        async for item in self.agentic_flow.run_stream(task=json.dumps(agent_input)):
            yield item

    async def process_question(
        self,
        task: str,
        chat_history: list[str] = None,
        parameters: dict = None,
    ) -> AsyncGenerator[Any, None]:
        """Process the complete question through the unified system.

        Args:
        ----
            task (str): The user question to process.
            chat_history (list[str], optional): The chat history. Defaults to None.
            parameters (dict, optional): Parameters to pass to agents. Defaults to None.

        Returns:
        -------
            AsyncGenerator[Any, None]: Stream of responses from the system.
        """
        logging.info("Processing question: %s", task)
        logging.info("Chat history: %s", chat_history)

        # Create input for initial flow
        agent_input = {
            "user_question": task,
            "chat_history": {},
            "parameters": parameters,
        }

        if chat_history is not None:
            for idx, chat in enumerate(chat_history):
                agent_input[f"chat_{idx}"] = chat

        # Run through the flow to get rewritten queries
        messages = []
        async for item in self.agentic_flow.run_stream(task=json.dumps(agent_input)):
            if hasattr(item, 'messages'):
                messages.extend(item.messages)
            elif hasattr(item, 'chat_message'):
                messages.append(item.chat_message)
            yield item
        
        try:
            # Extract rewritten queries from the result
            rewrite_message = next(
                (m for m in messages if m.source == "query_rewrite_agent"),
                None
            )
            
            if not rewrite_message:
                return
                
            rewrite_content = json.loads(rewrite_message.content)
            sub_queries = rewrite_content.get("sub_queries", [])
            
            if not sub_queries:
                return
            
            # Process independent sub-queries in parallel
            independent_queries = [q for q in sub_queries if not q.get("depends_on", [])]
            dependent_queries = [q for q in sub_queries if q.get("depends_on", [])]
            
            # Execute independent queries in parallel
            tasks = [
                self.process_sub_query(query, parameters)
                for query in independent_queries
            ]
            
            # Process each task's stream
            for task_stream in asyncio.as_completed(tasks):
                async for item in await task_stream:
                    yield item
            
            # Process dependent queries sequentially
            for query in dependent_queries:
                # Check if dependencies are met
                dependencies = query.get("depends_on", [])
                all_results = messages  # Use all messages to check dependencies
                dependencies_met = all(
                    any(m.source == dep for m in all_results)
                    for dep in dependencies
                )
                
                if dependencies_met:
                    # Add dependency results to query context
                    query["dependency_results"] = {
                        dep: next(m for m in all_results if m.source == dep)
                        for dep in dependencies
                    }
                    async for item in self.process_sub_query(query, parameters):
                        yield item
            
            # Send combined results to answer_and_sources_agent
            combined_input = {
                "original_question": task,
                "messages": messages,
                "combination_logic": rewrite_content.get("combination_logic", "")
            }
            
            yield TaskResult(messages=messages)
            
        except (json.JSONDecodeError, AttributeError, StopIteration):
            # Return the initial messages if any errors occur
            yield TaskResult(messages=messages)
