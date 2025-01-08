# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    AgentMessage,
    ChatMessage,
    TextMessage,
    ToolCallResultMessage,
)
from autogen_core import CancellationToken
import json
import logging
from autogen_text_2_sql.inner_autogen_text_2_sql import InnerAutoGenText2Sql
from aiostream import stream
from json import JSONDecodeError
import re
import os


class ParallelQuerySolvingAgent(BaseChatAgent):
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
    ) -> AsyncGenerator[AgentMessage | Response, None]:
        last_response = messages[-1].content
        parameter_input = messages[0].content
        try:
            injected_parameters = json.loads(parameter_input)["injected_parameters"]
        except json.JSONDecodeError:
            logging.error("Error decoding the user parameters.")
            injected_parameters = {}

        # Load the json of the last message to populate the final output object
        question_rewrites = json.loads(last_response)

        logging.info(f"Query Rewrites: {question_rewrites}")

        async def consume_inner_messages_from_agentic_flow(
            agentic_flow, identifier, database_results
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
                if identifier not in database_results:
                    database_results[identifier] = []

                logging.info(f"Checking Inner Message: {inner_message}")

                try:
                    if isinstance(inner_message, ToolCallResultMessage):
                        for call_result in inner_message.content:
                            # Check for SQL query results
                            parsed_message = self.parse_inner_message(
                                call_result.content
                            )
                            logging.info(f"Inner Loaded: {parsed_message}")

                            if isinstance(parsed_message, dict):
                                if (
                                    "type" in parsed_message
                                    and parsed_message["type"]
                                    == "query_execution_with_limit"
                                ):
                                    logging.info("Contains query results")
                                    database_results[identifier].append(
                                        {
                                            "sql_query": parsed_message[
                                                "sql_query"
                                            ].replace("\n", " "),
                                            "sql_rows": parsed_message["sql_rows"],
                                        }
                                    )

                    elif isinstance(inner_message, TextMessage):
                        parsed_message = self.parse_inner_message(inner_message.content)

                        logging.info(f"Inner Loaded: {parsed_message}")

                        # Search for specific message types and add them to the final output object
                        if isinstance(parsed_message, dict):
                            if ("contains_pre_run_results" in parsed_message) and (
                                parsed_message["contains_pre_run_results"] is True
                            ):
                                logging.info("Contains pre-run results")
                                for pre_run_sql_query, pre_run_result in parsed_message[
                                    "cached_questions_and_schemas"
                                ].items():
                                    database_results[identifier].append(
                                        {
                                            "sql_query": pre_run_sql_query.replace(
                                                "\n", " "
                                            ),
                                            "sql_rows": pre_run_result["sql_rows"],
                                        }
                                    )

                except Exception as e:
                    logging.warning(f"Error processing message: {e}")

                yield inner_message

        inner_solving_generators = []
        database_results = {}

        # Convert all_non_database_query to lowercase string and compare
        all_non_database_query = str(
            question_rewrites.get("all_non_database_query", "false")
        ).lower()

        if all_non_database_query == "true":
            yield Response(
                chat_message=TextMessage(
                    content="All queries are non-database queries. Nothing to process.",
                    source=self.name,
                ),
            )
            return

        # Start processing sub-queries
        for question_rewrite in question_rewrites["sub_questions"]:
            logging.info(f"Processing sub-query: {question_rewrite}")
            # Create an instance of the InnerAutoGenText2Sql class
            inner_autogen_text_2_sql = InnerAutoGenText2Sql(**self.kwargs)

            identifier = ", ".join(question_rewrite)

            # Add database connection info to injected parameters
            query_params = injected_parameters.copy() if injected_parameters else {}
            if "Text2Sql__DatabaseConnectionString" in os.environ:
                query_params["database_connection_string"] = os.environ[
                    "Text2Sql__DatabaseConnectionString"
                ]
            if "Text2Sql__DatabaseName" in os.environ:
                query_params["database_name"] = os.environ["Text2Sql__DatabaseName"]

            # Launch tasks for each sub-query
            inner_solving_generators.append(
                consume_inner_messages_from_agentic_flow(
                    inner_autogen_text_2_sql.process_question(
                        question=question_rewrite,
                        injected_parameters=query_params,
                    ),
                    identifier,
                    database_results,
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
                    logging.debug(f"Inner Solving Message: {inner_message}")
                    yield inner_message

        # Log final results for debugging or auditing
        logging.info(f"Database Results: {database_results}")

        # Final response
        yield Response(
            chat_message=TextMessage(
                content=json.dumps(
                    {"contains_results": True, "results": database_results}
                ),
                source=self.name,
            ),
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
