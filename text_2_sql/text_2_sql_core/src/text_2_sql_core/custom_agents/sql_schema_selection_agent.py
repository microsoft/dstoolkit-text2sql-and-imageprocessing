# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.factory import ConnectorFactory
import logging
from text_2_sql_core.prompts.load import load
from jinja2 import Template
import asyncio
from text_2_sql_core.structured_outputs.sql_schema_selection_agent import (
    SQLSchemaSelectionAgentOutput,
)


class SqlSchemaSelectionAgentCustomAgent:
    def __init__(self, **kwargs):
        self.ai_search_connector = ConnectorFactory.get_ai_search_connector()

        self.open_ai_connector = ConnectorFactory.get_open_ai_connector()

        self.sql_connector = ConnectorFactory.get_database_connector()

        system_prompt = load("sql_schema_selection_agent")["system_message"]

        self.system_prompt = Template(system_prompt).render(kwargs)

    async def process_message(self, user_questions: list[str]) -> dict:
        logging.info(f"User questions: {user_questions}")

        entity_tasks = []

        for user_question in user_questions:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_question},
            ]
            entity_tasks.append(
                self.open_ai_connector.run_completion_request(
                    messages, response_format=SQLSchemaSelectionAgentOutput
                )
            )

        entity_results = await asyncio.gather(*entity_tasks)

        entity_search_tasks = []
        column_search_tasks = []

        for entity_result in entity_results:
            logging.info(f"Entity result: {entity_result}")

            for entity_group in entity_result.entities:
                entity_search_tasks.append(
                    self.sql_connector.get_entity_schemas(
                        " ".join(entity_group), as_json=False
                    )
                )

            for filter_condition in entity_result.filter_conditions:
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

        final_results = {
            "COLUMN_OPTIONS_AND_VALUES_FOR_FILTERS": column_value_results,
            "SCHEMA_OPTIONS": final_schemas,
        }

        logging.info(f"Final results: {final_results}")

        return final_results
