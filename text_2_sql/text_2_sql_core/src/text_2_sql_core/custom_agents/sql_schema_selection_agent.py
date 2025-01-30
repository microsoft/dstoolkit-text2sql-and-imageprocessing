# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from typing import Any, Dict, List, Optional, Tuple
import logging
import asyncio

from jinja2 import Template

from text_2_sql_core.connectors.factory import ConnectorFactory
from text_2_sql_core.prompts.load import load
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
        self.current_database = None
        self.schema_cache = {}
        self.last_schema_update = {}  # Track when schemas were last updated

    async def verify_database_connection(self, db_path: str) -> bool:
        """Verify database connection and update schema cache.

        Args:
            db_path: Path to the database

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Set database path in connector
            self.sql_connector.current_db_path = db_path

            # Try to get schema information
            schemas = await self.sql_connector.get_entity_schemas("", as_json=False)
            if schemas and isinstance(schemas, dict) and "entities" in schemas:
                # Update schema cache with case-sensitive information
                self.schema_cache[db_path] = {
                    entity["Entity"].lower(): entity for entity in schemas["entities"]
                }
                self.last_schema_update[db_path] = asyncio.get_event_loop().time()
                logging.info(f"Updated schema cache for {db_path}")
                return True

            logging.warning(f"No schemas found for database: {db_path}")
            return False
        except Exception as e:
            logging.error(f"Failed to verify database connection: {e}")
            return False

    async def process_message(self, user_questions: list[str]) -> dict:
        """Process user questions and return relevant schema information.

        Args:
            user_questions: List of user questions to process

        Returns:
            Dictionary containing schema options and column values
        """
        logging.info(f"Processing questions: {user_questions}")

        # Get current database path
        current_db_path = os.environ.get("Text2Sql__DatabaseConnectionString", "")
        if not current_db_path:
            logging.error("Database connection string not set")
            return self._error_response("Database connection string not set")

        # Handle database switch or initial connection
        if current_db_path != self.current_database:
            logging.info(
                f"Switching database from {self.current_database} to {current_db_path}"
            )
            if not await self.verify_database_connection(current_db_path):
                return self._error_response(
                    f"Failed to connect to database: {current_db_path}"
                )
            self.current_database = current_db_path

        # Process questions to identify entities and filters
        entity_results = await self._process_questions(user_questions)
        if not entity_results:
            return self._error_response("Failed to process questions")

        # Get schemas for identified entities
        schemas_by_db = await self._get_schemas_for_entities(entity_results)
        if not schemas_by_db:
            logging.warning("No schemas found for entities")

        # Get column values for filters
        column_values = await self._get_column_values(entity_results)

        # Select most relevant database and schemas
        selected_db, final_schemas = self._select_database_and_schemas(
            schemas_by_db, current_db_path
        )

        # Construct final response
        final_results = {
            "COLUMN_OPTIONS_AND_VALUES_FOR_FILTERS": column_values,
            "SCHEMA_OPTIONS": final_schemas,
            "SELECTED_DATABASE": selected_db,
        }

        logging.info(f"Returning results for database: {selected_db}")
        return final_results

    def _error_response(self, error_message: str) -> dict:
        """Create an error response dictionary.

        Args:
            error_message: Error message to include

        Returns:
            Error response dictionary
        """
        logging.error(error_message)
        return {
            "COLUMN_OPTIONS_AND_VALUES_FOR_FILTERS": [],
            "SCHEMA_OPTIONS": [],
            "SELECTED_DATABASE": None,
            "ERROR": error_message,
        }

    async def _process_questions(
        self, user_questions: list[str]
    ) -> List[SQLSchemaSelectionAgentOutput]:
        """Process user questions to identify entities and filters.

        Args:
            user_questions: List of questions to process

        Returns:
            List of processed results
        """
        entity_tasks = []
        for question in user_questions:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question},
            ]
            # Get the JSON schema from the Pydantic model
            schema = SQLSchemaSelectionAgentOutput.model_json_schema()
            entity_tasks.append(
                self.open_ai_connector.run_completion_request(
                    messages, response_format=schema
                )
            )

        try:
            results = await asyncio.gather(*entity_tasks)
            # Convert the JSON results back to Pydantic models
            return [
                SQLSchemaSelectionAgentOutput.model_validate(result)
                for result in results
            ]
        except Exception as e:
            logging.error(f"Error processing questions: {e}")
            return []

    async def _get_schemas_for_entities(
        self, entity_results: List[SQLSchemaSelectionAgentOutput]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get schemas for identified entities.

        Args:
            entity_results: List of entity processing results

        Returns:
            Dictionary mapping database paths to schema lists
        """
        schemas_by_db = {}

        for result in entity_results:
            for entity_group in result.entities:
                search_text = " ".join(entity_group)
                schemas = await self._get_schemas_for_search(search_text)

                if schemas:
                    for schema in schemas:
                        db_path = schema.get("DatabasePath", self.current_database)
                        if db_path not in schemas_by_db:
                            schemas_by_db[db_path] = []
                        if schema not in schemas_by_db[db_path]:
                            schemas_by_db[db_path].append(schema)

        return schemas_by_db

    async def _get_schemas_for_search(self, search_text: str) -> List[Dict[str, Any]]:
        """Get schemas matching search text.

        Args:
            search_text: Text to search for

        Returns:
            List of matching schemas
        """
        # First check cache
        if self.current_database in self.schema_cache:
            cached_schemas = []
            search_terms = search_text.lower().split()
            for schema in self.schema_cache[self.current_database].values():
                if any(term in schema["Entity"].lower() for term in search_terms):
                    cached_schemas.append(schema)
            if cached_schemas:
                return cached_schemas

        # Get fresh schemas from connector
        try:
            schemas = await self.sql_connector.get_entity_schemas(
                search_text, as_json=False
            )
            if schemas and schemas.get("entities"):
                return schemas["entities"]
        except Exception as e:
            logging.error(f"Error getting schemas for '{search_text}': {e}")

        return []

    async def _get_column_values(
        self, entity_results: List[SQLSchemaSelectionAgentOutput]
    ) -> List[Any]:
        """Get column values for filter conditions.

        Args:
            entity_results: List of entity processing results

        Returns:
            List of column values
        """
        column_values = []

        for result in entity_results:
            for filter_condition in result.filter_conditions:
                try:
                    values = await self.sql_connector.get_column_values(
                        filter_condition, as_json=False
                    )
                    if isinstance(values, list):
                        column_values.extend(values)
                    elif isinstance(values, dict):
                        column_values.append(values)
                except Exception as e:
                    logging.error(
                        f"Error getting column values for '{filter_condition}': {e}"
                    )

        return column_values

    def _select_database_and_schemas(
        self, schemas_by_db: Dict[str, List[Dict[str, Any]]], current_db_path: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Select most relevant database and its schemas.

        Args:
            schemas_by_db: Dictionary mapping database paths to schema lists
            current_db_path: Current database path

        Returns:
            Tuple of (selected database path, final schemas list)
        """
        if not schemas_by_db:
            return current_db_path, []

        # Select database with most matching schemas
        selected_db = max(
            schemas_by_db.items(),
            key=lambda x: len(x[1]),
            default=(current_db_path, []),
        )[0]

        # Get schemas for selected database
        final_schemas = schemas_by_db.get(selected_db, [])

        # If no schemas found, try cache
        if not final_schemas and selected_db in self.schema_cache:
            final_schemas = list(self.schema_cache[selected_db].values())

        return selected_db, final_schemas
