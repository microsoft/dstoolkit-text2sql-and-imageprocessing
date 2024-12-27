# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    AgentMessage,
    ChatMessage,
    TextMessage,
)
from autogen_core import CancellationToken
import json
import logging
from autogen_text_2_sql.inner_autogen_text_2_sql import InnerAutoGenText2Sql

from aiostream import stream


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
            user_parameters = json.loads(parameter_input)["parameters"]
        except json.JSONDecodeError:
            logging.error("Error decoding the user parameters.")
            user_parameters = {}

        # Load the json of the last message to populate the final output object
        query_rewrites = json.loads(last_response)

        logging.info(f"Query Rewrites: {query_rewrites}")

        async def consume_inner_messages_from_agentic_flow(
            agentic_flow, identifier, complete_inner_messages
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
                if identifier not in complete_inner_messages:
                    complete_inner_messages[identifier] = []
                complete_inner_messages[identifier].append(inner_message)

                yield inner_message

        inner_solving_generators = []
        complete_inner_messages = {}

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
                        question=query_rewrite, parameters=user_parameters
                    ),
                    query_rewrite,
                    complete_inner_messages,
                )
            )

        logging.info("Created %i Inner Solving Generators", inner_solving_generators)
        logging.info("Starting Inner Solving Generators")
        combined_message_streams = stream.merge(*inner_solving_generators)

        async with combined_message_streams.stream() as streamer:
            async for inner_message in streamer:
                logging.info(f"Inner Solving Message: {inner_message}")
                yield inner_message

        # Log final results for debugging or auditing
        logging.info(f"Formatted Results: {complete_inner_messages}")

        # TODO: Trim out unnecessary information from the final response
        # Final response
        yield Response(
            chat_message=TextMessage(
                content=json.dumps(complete_inner_messages), source=self.name
            ),
            inner_messages=[
                complete_inner_message["message"]
                for complete_inner_message in complete_inner_messages
            ],
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
