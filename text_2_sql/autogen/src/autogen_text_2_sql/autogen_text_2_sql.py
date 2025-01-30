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
from autogen_text_2_sql.state_store import StateStore
from autogen_agentchat.messages import TextMessage
import json
import os
import re

from text_2_sql_core.payloads.interaction_payloads import (
    UserMessagePayload,
    AnswerWithSourcesPayload,
    DismabiguationRequestsPayload,
    ProcessingUpdatePayload,
    InteractionPayload,
    PayloadType,
    DEFAULT_INJECTED_PARAMETERS,
)
from autogen_agentchat.base import TaskResult
from typing import AsyncGenerator


class AutoGenText2Sql:
    def __init__(self, state_store: StateStore, **kwargs):
        self.target_engine = os.environ["Text2Sql__DatabaseEngine"].upper()

        if not state_store:
            raise ValueError("State store must be provided")
        self.state_store = state_store

        if "use_case" not in kwargs:
            logging.warning(
                "No use case provided. It is advised to provide a use case to help the LLM reason."
            )

        self.kwargs = {**DEFAULT_INJECTED_PARAMETERS, **kwargs}

        self._agentic_flow = None

    def get_all_agents(self):
        """Get all agents for the complete flow."""

        self.user_message_rewrite_agent = LLMAgentCreator.create(
            "user_message_rewrite_agent", **self.kwargs
        )

        self.parallel_query_solving_agent = ParallelQuerySolvingAgent(
            **self.kwargs)

        self.answer_agent = LLMAgentCreator.create("answer_agent", **self.kwargs)

        agents = [
            self.user_message_rewrite_agent,
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
            | TextMentionTermination("contains_disambiguation_requests")
            | MaxMessageTermination(5)
        )
        return termination

    def unified_selector(self, messages):
        """Unified selector for the complete flow."""
        logging.info("Messages: %s", messages)
        current_agent = messages[-1].source if messages else "user"
        decision = None

        # If this is the first message start with user_message_rewrite_agent
        if current_agent == "user":
            decision = "user_message_rewrite_agent"
        # Handle transition after query rewriting
        elif current_agent == "user_message_rewrite_agent":
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
<<<<<<< HEAD
        model_name = os.environ.get("OpenAI__GroupChatModel", "4o")
        logging.info(f"Creating group chat with model: {model_name}")
        logging.info(f"Environment variables:")
        logging.info(f"  OpenAI__GroupChatModel: {
                     os.environ.get('OpenAI__GroupChatModel')}")
        logging.info(f"  OpenAI__CompletionDeployment: {
                     os.environ.get('OpenAI__CompletionDeployment')}")
        logging.info(f"  OpenAI__MiniCompletionDeployment: {
                     os.environ.get('OpenAI__MiniCompletionDeployment')}")
=======

        if self._agentic_flow is not None:
            return self._agentic_flow
>>>>>>> upstream/main

        flow = SelectorGroupChat(
            self.get_all_agents(),
            allow_repeated_speaker=False,
            model_client=LLMModelCreator.get_model(model_name),
            termination_condition=self.termination_condition,
            selector_func=self.unified_selector,
        )

        self._agentic_flow = flow
        return self._agentic_flow

    def parse_message_content(self, content):
        """Parse different message content formats into a dictionary."""
        if isinstance(content, (list, dict)):
            # If it's already a list or dict, convert to JSON string
            return json.dumps(content)

        # Try to extract JSON from markdown-style code blocks
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try parsing as regular JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # If all parsing attempts fail, return the content as-is
        return content

    def extract_decomposed_user_messages(self, messages: list) -> list[list[str]]:
        """Extract the decomposed messages from the answer."""
        # Only load sub-message results if we have a database result
        sub_message_results = self.parse_message_content(messages[1].content)
        logging.info("Decomposed Results: %s", sub_message_results)

        decomposed_user_messages = sub_message_results.get(
            "decomposed_user_messages", []
        )

        logging.debug(
            "Returning decomposed_user_messages: %s", decomposed_user_messages
        )

        return decomposed_user_messages

    def extract_disambiguation_request(
        self, messages: list
    ) -> DismabiguationRequestsPayload:
        """Extract the disambiguation request from the answer."""
        all_disambiguation_requests = self.parse_message_content(messages[-1].content)

        decomposed_user_messages = self.extract_decomposed_user_messages(messages)
        request_payload = DismabiguationRequestsPayload(
            decomposed_user_messages=decomposed_user_messages
        )

        for per_question_disambiguation_request in all_disambiguation_requests[
            "disambiguation_requests"
        ].values():
            for disambiguation_request in per_question_disambiguation_request:
                logging.info(
                    "Disambiguation Request Identified: %s", disambiguation_request
                )

                request = DismabiguationRequestsPayload.Body.DismabiguationRequest(
                    assistant_question=disambiguation_request["assistant_question"],
                    user_choices=disambiguation_request["user_choices"],
                )
                request_payload.body.disambiguation_requests.append(request)

        return request_payload

    def extract_answer_payload(self, messages: list) -> AnswerWithSourcesPayload:
        """Extract the sources from the answer."""
        answer = messages[-1].content
        sql_query_results = self.parse_message_content(messages[-2].content)

        try:
            if isinstance(sql_query_results, str):
                sql_query_results = json.loads(sql_query_results)
        except json.JSONDecodeError:
            logging.warning(
                "Unable to read SQL query results: %s", sql_query_results)
            sql_query_results = {}
<<<<<<< HEAD
            sub_question_results = {}
        else:
            # Only load sub-question results if we have a database result
            sub_question_results = self.parse_message_content(
                messages[1].content)
            logging.info("Sub-Question Results: %s", sub_question_results)
=======
>>>>>>> upstream/main

        try:
            decomposed_user_messages = self.extract_decomposed_user_messages(messages)

            logging.info("SQL Query Results: %s", sql_query_results)
            payload = AnswerWithSourcesPayload(
                answer=answer, decomposed_user_messages=decomposed_user_messages
            )

            if not isinstance(sql_query_results, dict):
                logging.error(f"Expected dict, got {type(sql_query_results)}")
                return payload

<<<<<<< HEAD
            if "results" not in sql_query_results:
                logging.error("No 'results' key in sql_query_results")
                return payload

            # Extract queries and check if we need to combine them
            sql_queries = []
            for question, sql_query_result_list in sql_query_results["results"].items():
                if not sql_query_result_list:  # Check if list is empty
                    logging.warning(f"No results for question: {question}")
=======
            if "database_results" not in sql_query_results:
                logging.warning("No 'database_results' key in sql_query_results")
                return payload

            for message, sql_query_result_list in sql_query_results[
                "database_results"
            ].items():
                if not sql_query_result_list:  # Check if list is empty
                    logging.warning(f"No results for message: {message}")
>>>>>>> upstream/main
                    continue

                for sql_query_result in sql_query_result_list:
                    if not isinstance(sql_query_result, dict):
                        logging.error(
<<<<<<< HEAD
                            f"Expected dict for sql_query_result, got {
                                type(sql_query_result)}"
                        )
                        continue

                    if (
                        "sql_query" not in sql_query_result
                        or "sql_rows" not in sql_query_result
                    ):
                        logging.error(
                            "Missing required keys in sql_query_result")
                        continue

                    sql_queries.append(sql_query_result["sql_query"])

            # If we have multiple queries and combination_logic, combine them
            if len(sql_queries) > 1 and "combination_logic" in sub_question_results:
                combination_logic = sub_question_results["combination_logic"]
                # If the logic mentions filtering or conditions from first query
                if any(word in combination_logic.lower() for word in ["first", "then", "filter", "where"]):
                    # Extract WHERE clause from first query if it exists
                    where_clause = ""
                    first_query = sql_queries[0]
                    where_match = re.search(
                        r"WHERE\s+(.*?)(?:;|$)", first_query, re.IGNORECASE)
                    if where_match:
                        where_clause = f" WHERE {where_match.group(1)}"

                    # Add WHERE clause to second query
                    second_query = sql_queries[1]
                    if "WHERE" in second_query.upper():
                        # Replace existing WHERE clause
                        combined_query = re.sub(
                            r"WHERE\s+.*?(?:;|$)", where_clause + ";", second_query, flags=re.IGNORECASE)
                    else:
                        # Add WHERE clause before any semicolon
                        combined_query = second_query.replace(
                            ";", "") + where_clause + ";"

                    # Create source with combined query
                    source = AnswerWithSourcesPayload.Body.Source(
                        sql_query=combined_query,
                        sql_rows=sql_query_result["sql_rows"],
                    )
                    payload.body.sources.append(source)
                else:
                    # If no clear combination logic, add queries separately
                    for sql_query_result in sql_query_result_list:
                        source = AnswerWithSourcesPayload.Body.Source(
                            sql_query=sql_query_result["sql_query"],
                            sql_rows=sql_query_result["sql_rows"],
                        )
                        payload.body.sources.append(source)
            else:
                # Single query or no combination logic, add as-is
                for question, sql_query_result_list in sql_query_results["results"].items():
                    for sql_query_result in sql_query_result_list:
                        source = AnswerWithSourcesPayload.Body.Source(
                            sql_query=sql_query_result["sql_query"],
                            sql_rows=sql_query_result["sql_rows"],
=======
                            "Expected dict for sql_query_result, got %s",
                            type(sql_query_result),
>>>>>>> upstream/main
                        )
                        continue

                    if (
                        "sql_query" not in sql_query_result
                        or "sql_rows" not in sql_query_result
                    ):
                        logging.error("Missing required keys in sql_query_result")
                        continue

                    source = AnswerWithSourcesPayload.Body.Source(
                        sql_query=sql_query_result["sql_query"],
                        sql_rows=sql_query_result["sql_rows"],
                    )
                    payload.body.sources.append(source)

            if not payload.body.sources:
                logging.error("No valid sources extracted")

            if not payload.body.sources:
                logging.error("No valid sources extracted")

            return payload

        except Exception as e:
            logging.error("Error processing results: %s", str(e))
            # Return payload with error context instead of empty
            return AnswerWithSourcesPayload(
                answer=f"{answer}\nError processing results: {str(e)}"
            )

    async def process_user_message(
        self,
        thread_id: str,
        message_payload: UserMessagePayload,
    ) -> AsyncGenerator[InteractionPayload, None]:
        """Process the complete message through the unified system.

        Args:
        ----
            thread_id (str): The ID of the thread the message belongs to.
            task (str): The user message to process.
            injected_parameters (dict, optional): Parameters to pass to agents. Defaults to None.

        Returns:
        -------
            dict: The response from the system.
        """
        logging.info("Processing message: %s", message_payload.body.user_message)

        agent_input = {
            "message": message_payload.body.user_message,
            "injected_parameters": message_payload.body.injected_parameters,
        }

        state = self.state_store.get_state(thread_id)
        if state is not None:
            await self.agentic_flow.load_state(state)

        async for message in self.agentic_flow.run_stream(task=json.dumps(agent_input)):
            logging.debug("Message: %s", message)

            payload = None

            if isinstance(message, TextMessage):
                if message.source == "user_message_rewrite_agent":
                    payload = ProcessingUpdatePayload(
                        message="Rewriting the query...",
                    )
                elif message.source == "parallel_query_solving_agent":
                    payload = ProcessingUpdatePayload(
                        message="Solving the query...",
                    )
                elif message.source == "answer_agent":
                    payload = ProcessingUpdatePayload(
                        message="Generating the answer...",
                    )

            elif isinstance(message, TaskResult):
                # Now we need to return the final answer or the disambiguation request
                logging.info("TaskResult: %s", message)

                if message.messages[-1].source == "answer_agent":
                    # If the message is from the answer_agent, we need to return the final answer
                    payload = self.extract_answer_payload(message.messages)
                elif message.messages[-1].source == "parallel_query_solving_agent":
                    # Load into disambiguation request
<<<<<<< HEAD
                    payload = self.extract_disambiguation_request(
                        message.messages)
                elif message.messages[-1].source == "question_rewrite_agent":
=======
                    payload = self.extract_disambiguation_request(message.messages)
                elif message.messages[-1].source == "user_message_rewrite_agent":
>>>>>>> upstream/main
                    # Load into empty response
                    payload = AnswerWithSourcesPayload(
                        answer="Apologies, I cannot answer that message as it is not relevant. Please try another message or rephrase your current message."
                    )
            else:
                logging.error("Unexpected TaskResult: %s", message)
                raise ValueError("Unexpected TaskResult")

            if (
                payload is not None
                and payload.payload_type is PayloadType.PROCESSING_UPDATE
            ):
                logging.debug("Payload: %s", payload)
                yield payload

        # Return the final payload
        if (
            payload is not None
            and payload.payload_type is not PayloadType.PROCESSING_UPDATE
        ):
            # Get the state
            assistant_state = await self.agentic_flow.save_state()
            self.state_store.save_state(thread_id, assistant_state)

            logging.debug("Final Payload: %s", payload)

            yield payload
