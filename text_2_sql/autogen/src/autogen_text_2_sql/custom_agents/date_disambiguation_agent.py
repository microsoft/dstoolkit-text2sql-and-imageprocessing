# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core import CancellationToken
import logging


class DateDisambiguationAgent(BaseChatAgent):
    def __init__(self):
        super().__init__(
            "date_disambiguation_agent",
            "An agent that converts relative dates to absolute dates in user questions.",
        )

    @property
    def produced_message_types(self) -> List[type[ChatMessage]]:
        return [TextMessage]

    async def on_messages(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        # Calls the on_messages_stream
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
        logging.info("Processing date expressions in question: %s", user_question)

        # The actual date conversion will be handled by the LLM based on the YAML prompt
        yield Response(
            chat_message=TextMessage(
                content=user_question,
                source=self.name
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
