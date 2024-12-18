# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import AsyncGenerator, List, Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage
from autogen_core import CancellationToken
import json
from json import JSONDecodeError
import logging
import pandas as pd


class AnswerAndSourcesAgent(BaseChatAgent):
    def __init__(self):
        super().__init__(
            "answer_and_sources_agent",
            "An agent that formats the final answer and sources.",
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
        last_response = messages[-1].content

        # Load the json of the last message to populate the final output object
        final_output_object = json.loads(last_response)
        final_output_object["sources"] = []

        for message in messages:
            # Load the message content if it is a json object and was a query execution
            try:
                message = json.loads(message.content)
                logging.info(f"Loaded: {message}")

                # Search for specific message types and add them to the final output object
                if (
                    "type" in message
                    and message["type"] == "query_execution_with_limit"
                ):
                    dataframe = pd.DataFrame(message["sql_rows"])
                    final_output_object["sources"].append(
                        {
                            "sql_query": message["sql_query"].replace("\n", " "),
                            "sql_rows": message["sql_rows"],
                            "markdown_table": dataframe.to_markdown(index=False),
                        }
                    )

            except JSONDecodeError:
                logging.info(f"Could not load message: {message}")
                continue

            except Exception as e:
                logging.error(f"Error processing message: {e}")
                raise e

        yield Response(
            chat_message=TextMessage(
                content=json.dumps(final_output_object), source=self.name
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
