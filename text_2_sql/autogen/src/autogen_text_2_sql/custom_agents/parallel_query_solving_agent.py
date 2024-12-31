# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core import CancellationToken
import json
import logging
from autogen_text_2_sql.inner_autogen_text_2_sql import InnerAutoGenText2Sql
from aiostream import stream
from json import JSONDecodeError


class ParallelQuerySolvingAgent(BaseChatAgent):
    def __init__(self, engine_specific_rules: str, **kwargs: dict):
        super().__init__(
            "parallel_query_solving_agent",
            "An agent that solves each query in parallel.",
        )

        self.engine_specific_rules = engine_specific_rules
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
        query_rewrites = json.loads(last_response)

        logging.info(f"Query Rewrites: {query_rewrites}")

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

                if isinstance(inner_message, TaskResult) is False:
                    try:
                        inner_message = json.loads(inner_message.content)
                        logging.info(f"Loaded: {inner_message}")

                        # Search for specific message types and add them to the final output object
                        if (
                            "type" in inner_message
                            and inner_message["type"] == "query_execution_with_limit"
                        ):
                            database_results[identifier].append(
                                {
                                    "sql_query": inner_message["sql_query"].replace(
                                        "\n", " "
                                    ),
                                    "sql_rows": inner_message["sql_rows"],
                                }
                            )

                    except (JSONDecodeError, TypeError) as e:
                        logging.error("Could not load message: %s", inner_message)
                        logging.warning(f"Error processing message: {e}")

                    except Exception as e:
                        logging.error("Could not load message: %s", inner_message)
                        logging.error(f"Error processing message: {e}")
                        raise e

                yield inner_message

        inner_solving_generators = []
        database_results = {}

        # Start processing sub-queries
        for query_rewrite in query_rewrites["sub_queries"]:
            logging.info(f"Processing sub-query: {query_rewrite}")
            # Create an instance of the InnerAutoGenText2Sql class
            inner_autogen_text_2_sql = InnerAutoGenText2Sql(
                self.engine_specific_rules, **self.kwargs
            )

            # Launch tasks for each sub-query
            inner_solving_generators.append(
                consume_inner_messages_from_agentic_flow(
                    inner_autogen_text_2_sql.process_question(
                        question=query_rewrite, injected_parameters=injected_parameters
                    ),
                    query_rewrite,
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
