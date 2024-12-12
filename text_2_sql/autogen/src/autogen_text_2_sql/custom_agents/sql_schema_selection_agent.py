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
from text_2_sql_core.prompts.load import load
from jinja2 import Template
import asyncio


class SqlSchemaSelectionAgent(BaseChatAgent):
    def __init__(self, **kwargs):
        super().__init__(
            "sql_schema_selection_agent",
            "An agent that fetches the schemas from the cache based on the user question.",
        )

        self.ai_search_connector = ConnectorFactory.get_ai_search_connector()

        self.open_ai_connector = ConnectorFactory.get_open_ai_connector()

        self.sql_connector = ConnectorFactory.get_database_connector()

        system_prompt = load("sql_schema_selection_agent")["system_message"]

        self.system_prompt = Template(system_prompt).render(kwargs)

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

        # load the json of the last message and get the user question's

        user_questions = json.loads(last_response)

        logging.info(f"User questions: {user_questions}")

        entity_tasks = []

        for user_question in user_questions:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_question},
            ]
            entity_tasks.append(self.open_ai_connector.run_completion_request(messages))

        entity_results = await asyncio.gather(*entity_tasks)

        entity_search_tasks = []
        column_search_tasks = []

        for entity_result in entity_results:
            loaded_entity_result = json.loads(entity_result)

            logging.info(f"Loaded entity result: {loaded_entity_result}")

            for entity_group in loaded_entity_result["entities"]:
                entity_search_tasks.append(
                    self.sql_connector.get_entity_schemas(
                        " ".join(entity_group), as_json=False
                    )
                )

            for filter_condition in loaded_entity_result["filter_conditions"]:
                column_search_tasks.append(
                    self.ai_search_connector.get_column_values(
                        filter_condition, as_json=False
                    )
                )

        schemas_results = await asyncio.gather(*entity_search_tasks)
        column_value_results = await asyncio.gather(*column_search_tasks)

        # deduplicate schemas
        final_schemas = []

        for schema_result in schemas_results:
            for schema in schema_result:
                if schema not in final_schemas:
                    final_schemas.append(schema)

        columns_for_filter = {}
        values_for_filter = {}
        for filter, column_value_result in zip(
            loaded_entity_result["filter_conditions"], column_value_results
        ):
            columns_for_filter[filter] = []
            values_for_filter[filter] = []
            for column in column_value_result:
                if column["Column"] not in columns_for_filter[filter]:
                    columns_for_filter[filter].append(column["Column"])

                if column["Value"] not in values_for_filter[filter]:
                    values_for_filter[filter].append(column["Value"])

        num_all_values = [len(filter) for filter in values_for_filter]
        num_all_columns = [len(filter) for filter in columns_for_filter]

        final_results = {
            "MANDATORY_DISAMBIGUATION": max(num_all_values) > 3
            or max(num_all_columns) > 3,
            "COLUMN_OPTIONS_FOR_FILTERS": columns_for_filter,
            "VALUE_OPTIONS_FOR_FILTERS": values_for_filter,
            "SCHEMA_OPTIONS": final_schemas,
        }

        logging.info(f"Final results: {final_results}")

        yield Response(
            chat_message=TextMessage(
                content=json.dumps(final_results), source=self.name
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
