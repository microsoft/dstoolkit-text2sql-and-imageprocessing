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

    async def process_message(self, message: str) -> dict:
        logging.info(f"Processing message: {message}")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message},
        ]
        entity_result = await self.open_ai_connector.run_completion_request(
            messages, response_format=SQLSchemaSelectionAgentOutput
        )

        entity_search_tasks = []
        column_search_tasks = []

        logging.info(f"Entity result: {entity_result}")

        for entity_group in entity_result.entities:
            logging.info("Searching for schemas for entity group: %s", entity_group)
            entity_search_tasks.append(
                self.sql_connector.get_entity_schemas(
                    " ".join(entity_group), as_json=False
                )
            )

        for filter_condition in entity_result.filter_conditions:
            logging.info("Searching for column values for filter: %s", filter_condition)
            column_search_tasks.append(
                self.sql_connector.get_column_values(filter_condition, as_json=False)
            )

        schemas_results = await asyncio.gather(*entity_search_tasks)
        column_value_results = await asyncio.gather(*column_search_tasks)

        # Group schemas by database for Spider evaluation support
        schemas_by_db = {}
        for schema_result in schemas_results:
            for schema in schema_result:
                db_path = schema.get("DatabasePath")
                if db_path:
                    if db_path not in schemas_by_db:
                        schemas_by_db[db_path] = []
                    if schema not in schemas_by_db[db_path]:
                        schemas_by_db[db_path].append(schema)

        # Select most relevant database based on schema matches
        selected_db = None
        max_schemas = 0
        for db_path, schemas in schemas_by_db.items():
            if len(schemas) > max_schemas:
                max_schemas = len(schemas)
                selected_db = db_path

        # Set selected database in connector
        if selected_db:
            self.sql_connector.current_db_path = selected_db

        # Use schemas from selected database or all schemas if no database selection
        final_schemas = schemas_by_db.get(selected_db, []) if selected_db else []
        if not final_schemas:
            # Fallback to original deduplication if no database was selected
            for schema_result in schemas_results:
                for schema in schema_result:
                    if schema not in final_schemas:
                        final_schemas.append(schema)

        final_results = {
            "COLUMN_OPTIONS_AND_VALUES_FOR_FILTERS": column_value_results,
            "SCHEMA_OPTIONS": final_schemas,
            "SELECTED_DATABASE": selected_db,
        }

        logging.info(f"Final results: {final_results}")

        return final_results
