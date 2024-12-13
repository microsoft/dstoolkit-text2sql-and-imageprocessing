# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core import CancellationToken
from text_2_sql_core.connectors.factory import ConnectorFactory
import json
import logging


class SqlQueryCacheAgent(BaseChatAgent):
    def __init__(self):
        super().__init__(
            "sql_query_cache_agent",
            "An agent that fetches the queries from the cache based on the user question.",
        )

        self.sql_connector = ConnectorFactory.get_database_connector()

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
        # Get the decomposed questions from the query_rewrite_agent
        last_response = messages[-1].content
        try:
            user_questions = json.loads(last_response)
            logging.info(f"Processing questions: {user_questions}")

            # Initialize results dictionary
            cached_results = {
                "cached_questions_and_schemas": [],
                "contains_pre_run_results": False
            }

            # Process each question sequentially
            for question in user_questions:
                # Fetch the queries from the cache based on the question
                logging.info(f"Fetching queries from cache for question: {question}")
                cached_query = await self.sql_connector.fetch_queries_from_cache(question)
                
                # If any question has pre-run results, set the flag
                if cached_query.get("contains_pre_run_results", False):
                    cached_results["contains_pre_run_results"] = True
                
                # Add the cached results for this question
                if cached_query.get("cached_questions_and_schemas"):
                    cached_results["cached_questions_and_schemas"].extend(
                        cached_query["cached_questions_and_schemas"]
                    )

            logging.info(f"Final cached results: {cached_results}")
            yield Response(
                chat_message=TextMessage(
                    content=json.dumps(cached_results), source=self.name
                )
            )
        except json.JSONDecodeError:
            # If not JSON array, process as single question
            logging.info(f"Processing single question: {last_response}")
            cached_queries = await self.sql_connector.fetch_queries_from_cache(last_response)
            yield Response(
                chat_message=TextMessage(
                    content=json.dumps(cached_queries), source=self.name
                )
            )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
