# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core.base import CancellationToken
from text_2_sql.autogen.utils.sql import get_entity_schemas
from keybert import KeyBERT
import logging


class SqlSchemaExtractionAgent(BaseChatAgent):
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

        kw_model = KeyBERT()

        top_keywords = kw_model.extract_keywords(
            user_question, keyphrase_ngram_range=(1, 3), top_n=5
        )

        # Extract just the key phrases (ignoring the score)
        key_phrases = [keyword[0] for keyword in top_keywords]

        # Join them into a string list
        key_phrases_str = ", ".join(key_phrases)

        entity_schemas = await get_entity_schemas(key_phrases_str)

        logging.info(entity_schemas)

        yield Response(
            chat_message=TextMessage(content=entity_schemas, source=self.name)
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
