# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentEvent, ChatMessage, TextMessage
from autogen_core import CancellationToken
import json
import logging
from text_2_sql_core.custom_agents.sql_schema_selection_agent import (
    SqlSchemaSelectionAgentCustomAgent,
)


class SqlSchemaSelectionAgent(BaseChatAgent):
    def __init__(self, **kwargs):
        super().__init__(
            "sql_schema_selection_agent",
            "An agent that fetches the schemas from the cache based on the user input.",
        )

        self.agent = SqlSchemaSelectionAgentCustomAgent(**kwargs)

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
    ) -> AsyncGenerator[AgentEvent | Response, None]:
        # Try to parse as JSON first
        try:
            request_details = json.loads(messages[0].content)
            message = request_details["user_message"]
        except (json.JSONDecodeError, KeyError):
            # If not JSON or missing question key, use content directly
            message = messages[0].content

        logging.info("Processing message: %s", message)

        final_results = await self.agent.process_message(message)

        yield Response(
            chat_message=TextMessage(
                content=json.dumps(final_results), source=self.name
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
