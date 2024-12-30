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
from autogen_text_2_sql.custom_agents.parallel_query_solving_agent import (
    ParallelQuerySolvingAgent,
)
from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.messages import TextMessage
import json
import os
from datetime import datetime

from text_2_sql_core.payloads import (
    AnswerWithSources,
    UserInformationRequest,
    ProcessingUpdate,
)
from autogen_agentchat.base import Response, TaskResult
from typing import AsyncGenerator


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
        self.target_engine = os.environ["Text2Sql__DatabaseEngine"].upper()
        self.engine_specific_rules = engine_specific_rules
        self.kwargs = kwargs

    def get_all_agents(self):
        """Get all agents for the complete flow."""
        # Get current datetime for the Query Rewrite Agent
        current_datetime = datetime.now()

        self.query_rewrite_agent = LLMAgentCreator.create(
            "query_rewrite_agent", current_datetime=current_datetime
        )

        self.parallel_query_solving_agent = ParallelQuerySolvingAgent(
            engine_specific_rules=self.engine_specific_rules, **self.kwargs
        )

        self.answer_agent = LLMAgentCreator.create("answer_agent")

        # Auto-responding UserProxyAgent
        self.user_proxy = EmptyResponseUserProxyAgent(name="user_proxy")

        agents = [
            self.user_proxy,
            self.query_rewrite_agent,
            self.parallel_query_solving_agent,
            self.answer_agent,
        ]

        return agents

    @property
    def termination_condition(self):
        """Define the termination condition for the chat."""
        termination = (
            TextMentionTermination("TERMINATE")
            | SourceMatchTermination("answer_agent")
            | TextMentionTermination("requires_user_information_request")
            | MaxMessageTermination(5)
        )
        return termination

    def unified_selector(self, messages):
        """Unified selector for the complete flow."""
        logging.info("Messages: %s", messages)
        current_agent = messages[-1].source if messages else "user"
        decision = None

        # If this is the first message start with query_rewrite_agent
        if current_agent == "user":
            decision = "query_rewrite_agent"
        # Handle transition after query rewriting
        elif current_agent == "query_rewrite_agent":
            decision = "parallel_query_solving_agent"
        # Handle transition after parallel query solving
        elif current_agent == "parallel_query_solving_agent":
            decision = "answer_agent"

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

    def extract_sources(self, messages: list) -> AnswerWithSources:
        """Extract the sources from the answer."""

        answer = messages[-1].content

        sql_query_results = messages[-2].content

        try:
            sql_query_results = json.loads(sql_query_results)

            logging.info("SQL Query Results: %s", sql_query_results)

            sources = []

            for question, sql_query_result_list in sql_query_results["results"].items():
                logging.info(
                    "SQL Query Result for question '%s': %s",
                    question,
                    sql_query_result_list,
                )

                for sql_query_result in sql_query_result_list:
                    logging.info("SQL Query Result: %s", sql_query_result)
                    sources.append(
                        {
                            "sql_query": sql_query_result["sql_query"],
                            "sql_rows": sql_query_result["sql_rows"],
                        }
                    )

        except json.JSONDecodeError:
            logging.error("Could not load message: %s", sql_query_results)
            raise ValueError("Could not load message")

        return AnswerWithSources(
            answer=answer,
            sources=sources,
        )

    async def process_question(
        self,
        question: str,
        chat_history: list[str] = None,
        parameters: dict = None,
    ) -> AsyncGenerator[AnswerWithSources | UserInformationRequest, None]:
        """Process the complete question through the unified system.

        Args:
        ----
            task (str): The user question to process.
            chat_history (list[str], optional): The chat history. Defaults to None.
            parameters (dict, optional): Parameters to pass to agents. Defaults to None.

        Returns:
        -------
            dict: The response from the system.
        """
        logging.info("Processing question: %s", question)
        logging.info("Chat history: %s", chat_history)

        agent_input = {
            "question": question,
            "chat_history": {},
            "parameters": parameters,
        }

        if chat_history is not None:
            # Update input
            for idx, chat in enumerate(chat_history):
                agent_input[f"chat_{idx}"] = chat

        async for message in self.agentic_flow.run_stream(task=json.dumps(agent_input)):
            logging.debug("Message: %s", message)

            payload = None

            if isinstance(message, TextMessage):
                if message.source == "query_rewrite_agent":
                    # If the message is from the query_rewrite_agent, we need to update the chat history
                    payload = ProcessingUpdate(
                        message="Rewriting the query...",
                    )
                elif message.source == "parallel_query_solving_agent":
                    # If the message is from the parallel_query_solving_agent, we need to update the chat history
                    payload = ProcessingUpdate(
                        message="Solving the query...",
                    )
                elif message.source == "answer_agent":
                    # If the message is from the answer_agent, we need to update the chat history
                    payload = ProcessingUpdate(
                        message="Generating the answer...",
                    )

            elif isinstance(message, TaskResult):
                # Now we need to return the final answer or the disambiguation request
                logging.info("TaskResult: %s", message)

                if message.messages[-1].source == "answer_agent":
                    # If the message is from the answer_agent, we need to return the final answer
                    payload = self.extract_sources(message.messages)
                elif message.messages[-1].source == "parallel_query_solving_agent":
                    payload = UserInformationRequest(
                        **json.loads(message.messages[-1].content),
                    )
                else:
                    logging.error("Unexpected TaskResult: %s", message)
                    raise ValueError("Unexpected TaskResult")

            if payload is not None:
                logging.debug("Payload: %s", payload)
                yield payload
