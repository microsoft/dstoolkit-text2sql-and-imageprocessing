# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    AgentEvent,
    ChatMessage,
    TextMessage,
    ToolCallExecutionEvent,
)
from autogen_core import CancellationToken
import json
import logging
from autogen_text_2_sql.inner_autogen_text_2_sql import InnerAutoGenText2Sql
from aiostream import stream
from json import JSONDecodeError
import re
from pydantic import BaseModel, Field


class FilteredParallelMessagesCollection(BaseModel):
    """A collection of filtered parallel messages."""

    database_results: dict[str, list] = Field(default_factory=dict)
    disambiguation_requests: dict[str, list] = Field(default_factory=dict)

    def add_identifier(self, identifier: str):
        """Add an identifier to the collection.

        Args:
        ----
            identifier (str): The identifier to add."""
        if identifier not in self.database_results:
            self.database_results[identifier] = []
        if identifier not in self.disambiguation_requests:
            self.disambiguation_requests[identifier] = []


class ParallelQuerySolvingAgent(BaseChatAgent):
    """An agent that solves each query in parallel."""

    def __init__(self, **kwargs: dict):
        super().__init__(
            "parallel_query_solving_agent",
            "An agent that solves each query in parallel.",
        )

        self.kwargs = kwargs

    @property
    def produced_message_types(self) -> List[type[ChatMessage]]:
        return [TextMessage]

    async def on_messages(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        # Calls the on_messages_stream.
        response: Response | None = None
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                response = message
        assert response is not None
        return response

    def parse_inner_message(self, message):
        """Parse inner message content into a structured format."""
        try:
            if isinstance(message, (dict, list)):
                return message

            if not isinstance(message, str):
                message = str(message)

            # Try to parse as JSON first
            try:
                return json.loads(message)
            except JSONDecodeError:
                pass

            json_match = re.search(r"```json\s*(.*?)\s*```", message, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except JSONDecodeError:
                    pass

            # If we can't parse it, return it as-is
            return message
        except Exception as e:
            logging.warning(f"Error parsing message: {e}")
            return message

    async def on_messages_stream(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[AgentEvent | Response, None]:
        last_response = messages[-1].content
        parameter_input = messages[-2].content
        try:
            injected_parameters = json.loads(parameter_input)["injected_parameters"]
        except json.JSONDecodeError:
            logging.error("Error decoding the user parameters.")
            injected_parameters = {}

        # Load the json of the last message to populate the final output object
        sequential_steps = json.loads(last_response)

        logging.info("Sequential Steps: %s", sequential_steps)

        async def consume_inner_messages_from_agentic_flow(
            agentic_flow, identifier, filtered_parallel_messages
        ):
            """
            Consume the inner messages and append them to the specified list.

            Args:
            ----
                agentic_flow: The async generator to consume messages from.
                messages_list: The list to which messages should be added.
            """
            async for inner_message in agentic_flow:
                # Add message to results dictionary, tagged by the function name
                filtered_parallel_messages.add_identifier(identifier)

                logging.info("Checking Inner Message: %s", inner_message)

                try:
                    if isinstance(inner_message, ToolCallExecutionEvent):
                        for call_result in inner_message.content:
                            # Check for SQL query results
                            parsed_message = self.parse_inner_message(
                                call_result.content
                            )
                            logging.info("Inner Loaded: %s", parsed_message)

                            if isinstance(parsed_message, dict):
                                if (
                                    "type" in parsed_message
                                    and parsed_message["type"]
                                    == "query_execution_with_limit"
                                ):
                                    logging.info("Contains query results")
                                    filtered_parallel_messages.database_results[
                                        identifier
                                    ].append(
                                        {
                                            "sql_query": parsed_message["sql_query"],
                                            "sql_rows": parsed_message["sql_rows"],
                                        }
                                    )

                    elif isinstance(inner_message, TextMessage):
                        parsed_message = self.parse_inner_message(inner_message.content)

                        logging.info("Inner Loaded: %s", parsed_message)

                        # Search for specific message types and add them to the final output object
                        if isinstance(parsed_message, dict):
                            # Check if the message contains pre-run results
                            if (
                                "contains_cached_sql_queries_with_schemas_from_cache_database_results"
                                in parsed_message
                            ) and (
                                parsed_message[
                                    "contains_cached_sql_queries_with_schemas_from_cache_database_results"
                                ]
                                is True
                            ):
                                logging.info("Contains pre-run results")
                                for pre_run_sql_query, pre_run_result in parsed_message[
                                    "cached_messages_and_schemas"
                                ].items():
                                    filtered_parallel_messages.database_results[
                                        identifier
                                    ].append(
                                        {
                                            "sql_query": pre_run_sql_query.replace(
                                                "\n", " "
                                            ),
                                            "sql_rows": pre_run_result["sql_rows"],
                                        }
                                    )
                            # Check if disambiguation is required
                            elif ("disambiguation_requests" in parsed_message) and (
                                parsed_message["disambiguation_requests"]
                            ):
                                logging.info("Contains disambiguation requests")
                                for disambiguation_request in parsed_message[
                                    "disambiguation_requests"
                                ]:
                                    filtered_parallel_messages.disambiguation_requests[
                                        identifier
                                    ].append(disambiguation_request)

                except Exception as e:
                    logging.warning("Error processing message: %s", e)

                yield inner_message

        inner_solving_generators = []
        filtered_parallel_messages = FilteredParallelMessagesCollection()

        # Convert requires_sql_queries to lowercase string and compare
        requires_sql_queries = str(
            sequential_steps.get("requires_sql_queries", "false")
        ).lower()

        if requires_sql_queries == "false":
            yield Response(
                chat_message=TextMessage(
                    content="All queries are non-database queries. Nothing to process.",
                    source=self.name,
                ),
            )
            return

        # Start processing sub-queries
        for sequential_round in sequential_steps["steps"]:
            logging.info("Processing round: %s", sequential_round)

            for parallel_message in sequential_round:
                logging.info("Parallel Message: %s", parallel_message)

                # Create an instance of the InnerAutoGenText2Sql class
                inner_autogen_text_2_sql = InnerAutoGenText2Sql(**self.kwargs)

                # Launch tasks for each sub-query
                inner_solving_generators.append(
                    consume_inner_messages_from_agentic_flow(
                        inner_autogen_text_2_sql.process_user_message(
                            user_message=parallel_message,
                            injected_parameters=injected_parameters,
                            database_results=filtered_parallel_messages.database_results,
                        ),
                        parallel_message,
                        filtered_parallel_messages,
                    )
                )

            logging.info(
                "Created %i Inner Solving Generators", len(inner_solving_generators)
            )
            logging.info("Starting Inner Solving Generators")
            combined_message_streams = stream.merge(*inner_solving_generators)

            async with combined_message_streams.stream() as streamer:
                async for inner_message in streamer:
                    if isinstance(inner_message, TextMessage):
                        logging.debug("Inner Solving Message: %s", inner_message)
                        yield inner_message

            # Log final results for debugging or auditing
            logging.info(
                "Database Results: %s", filtered_parallel_messages.database_results
            )
            logging.info(
                "Disambiguation Requests: %s",
                filtered_parallel_messages.disambiguation_requests,
            )

            # Check for disambiguation requests before processing the next round

            if (
                max(
                    map(
                        len, filtered_parallel_messages.disambiguation_requests.values()
                    )
                )
                > 0
            ):
                # Final response
                yield Response(
                    chat_message=TextMessage(
                        content=json.dumps(
                            {
                                "contains_disambiguation_requests": True,
                                "disambiguation_requests": filtered_parallel_messages.disambiguation_requests,
                            }
                        ),
                        source=self.name,
                    ),
                )

                return

        # Final response
        yield Response(
            chat_message=TextMessage(
                content=json.dumps(
                    {
                        "contains_database_results": True,
                        "database_results": filtered_parallel_messages.database_results,
                    }
                ),
                source=self.name,
            ),
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
