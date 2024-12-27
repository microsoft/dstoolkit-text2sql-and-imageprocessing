# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    AgentEvent,
    AgentMessage,
    ChatMessage,
    TextMessage,
)
from autogen_core import CancellationToken
import json
import logging
import asyncio
from autogen_text_2_sql.inner_autogen_text_2_sql import InnerAutoGenText2Sql


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
        inner_messages: List[AgentEvent | ChatMessage] = []

        last_response = messages[-1].content
        parameter_input = messages[0].content
        last_response = messages[-1].content
        try:
            user_parameters = json.loads(parameter_input)["parameters"]
        except json.JSONDecodeError:
            logging.error("Error decoding the user parameters.")
            user_parameters = {}

        # Load the json of the last message to populate the final output object
        query_rewrites = json.loads(last_response)

        logging.info(f"Query Rewrite: {query_rewrites}")

        inner_solving_tasks = []

        for query_rewrite in query_rewrites["sub_queries"]:
            # Create an instance of the InnerAutoGenText2Sql class
            inner_autogen_text_2_sql = InnerAutoGenText2Sql(
                self.engine_specific_rules, **self.kwargs
            )

            inner_solving_tasks.append(
                inner_autogen_text_2_sql.process_question(
                    question=query_rewrite, parameters=user_parameters
                )
            )

        # Wait for all the inner solving tasks to complete
        inner_solving_results = await asyncio.gather(*inner_solving_tasks)

        logging.info(f"Inner Solving Results: {inner_solving_results}")

        yield Response(
            chat_message=TextMessage(
                content=json.dumps(inner_solving_results), source=self.name
            ),
            inner_messages=inner_messages,
        )

        async def on_reset(self, cancellation_token: CancellationToken) -> None:
            pass
