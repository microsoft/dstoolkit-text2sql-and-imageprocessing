# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core import CancellationToken
from text_2_sql_core.custom_agents.sql_query_cache_agent import (
    SqlQueryCacheAgentCustomAgent,
)
import json
import logging


class SqlQueryCacheAgent(BaseChatAgent):
    def __init__(self):
        super().__init__(
            "sql_query_cache_agent",
            "An agent that fetches the queries from the cache based on the user question.",
        )

        self.agent = SqlQueryCacheAgentCustomAgent()

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
        # Get the decomposed questions from the question_rewrite_agent
        try:
            request_details = json.loads(messages[0].content)
            injected_parameters = request_details["injected_parameters"]
            user_questions = request_details["question"]
            logging.info(f"Processing questions: {user_questions}")
            logging.info(f"Input Parameters: {injected_parameters}")
        except json.JSONDecodeError:
            # If not JSON array, process as single question
            raise ValueError("Could not load message")

        cached_results = await self.agent.process_message(
            user_questions, injected_parameters
        )
        yield Response(
            chat_message=TextMessage(
                content=json.dumps(cached_results), source=self.name
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
