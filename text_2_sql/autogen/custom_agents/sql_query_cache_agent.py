# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core.base import CancellationToken
from utils.sql_utils import fetch_queries_from_cache
import json
import logging


class SqlQueryCacheAgent(BaseChatAgent):
    def __init__(self):
        super().__init__(
            "sql_query_cache_agent",
            "An agent that fetches the queries from the cache based on the user question.",
        )

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
        user_question = messages[0].content

        # Fetch the queries from the cache based on the user question.
        logging.info("Fetching queries from cache based on the user question...")

        cached_queries = await fetch_queries_from_cache(user_question)

        yield Response(
            chat_message=TextMessage(
                content=json.dumps(cached_queries), source=self.name
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
