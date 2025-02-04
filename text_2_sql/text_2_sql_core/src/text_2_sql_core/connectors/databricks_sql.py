# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
from databricks import sql
from typing import Annotated
import asyncio
import os
import logging
import json

from text_2_sql_core.utils.database import DatabaseEngine, DatabaseEngineSpecificFields


class DatabricksSqlConnector(SqlConnector):
    def __init__(self):
        super().__init__()

        self.database_engine = DatabaseEngine.DATABRICKS

    @property
    def engine_specific_rules(self) -> str:
        """Get the engine specific rules."""
        return

    @property
    def engine_specific_fields(self) -> list[str]:
        """Get the engine specific fields."""
        return [DatabaseEngineSpecificFields.CATALOG]

    @property
    def invalid_identifiers(self) -> list[str]:
        """Get the invalid identifiers upon which a sql query is rejected."""
        return [
            # Session and system variables
            "CURRENT_CATALOG",
            "CURRENT_DATABASE",
            "CURRENT_USER",
            "SESSION_USER",
            "CURRENT_ROLE",
            "CURRENT_QUERY",
            "CURRENT_WAREHOUSE",
            "SESSION_ID",
            # System metadata functions
            "DATABASE",
            "USER",
            # Potentially unsafe built-in functions
            "CURRENT_USER",
            "SESSION_USER",
            "SYSTEM",
            "SHOW",
            "DESCRIBE",
            "EXPLAIN",
            "SET",
            "SHOW TABLES",
            "SHOW COLUMNS",
            "SHOW DATABASES",
        ]

    def sanitize_identifier(self, identifier: str) -> str:
        """Sanitize the identifier to ensure it is valid.

        Args:
        ----
            identifier (str): The identifier to sanitize.

        Returns:
        -------
            str: The sanitized identifier.
        """
        return f"`{identifier}`"

    async def query_execution(
        self,
        sql_query: Annotated[
            str,
            "The SQL query to run against the database.",
        ],
        cast_to: any = None,
        limit=None,
    ) -> list[dict]:
        """Run the SQL query against the database.

        Args:
        ----
            sql_query (str): The SQL query to run against the database.

        Returns:
        -------
            list[dict]: The results of the SQL query.
        """
        logging.info(f"Running query: {sql_query}")
        results = []

        # Set up connection parameters for Databricks SQL endpoint
        connection = sql.connect(
            server_hostname=os.environ["Text2Sql__Databricks__ServerHostname"],
            http_path=os.environ["Text2Sql__Databricks__HttpPath"],
            access_token=os.environ["Text2Sql__Databricks__AccessToken"],
        )

        try:
            # Create a cursor
            cursor = connection.cursor()

            # Execute the query in a thread-safe manner
            await asyncio.to_thread(cursor.execute, sql_query)

            # Fetch column names
            columns = [col[0] for col in cursor.description]

            # Fetch rows
            if limit is not None:
                rows = await asyncio.to_thread(cursor.fetchmany, limit)
            else:
                rows = await asyncio.to_thread(cursor.fetchall)

            # Process rows
            for row in rows:
                if cast_to is not None:
                    results.append(cast_to.from_sql_row(row, columns))
                else:
                    results.append(dict(zip(columns, row)))

        except Exception as e:
            logging.error(f"Error while executing query {sql_query}: {e}")
            raise e
        finally:
            cursor.close()
            connection.close()

        return results

    async def get_entity_schemas(
        self,
        text: Annotated[
            str,
            "The text to run a semantic search against. Relevant entities will be returned.",
        ],
        excluded_entities: Annotated[
            list[str],
            "The entities to exclude from the search results. Pass the entity property of entities (e.g. 'SalesLT.Address') you already have the schemas for to avoid getting repeated entities.",
        ] = [],
        as_json: bool = True,
    ) -> str:
        """Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
            str: The schema of the views or tables in JSON format.
        """

        schemas = await self.ai_search_connector.get_entity_schemas(
            text, excluded_entities, engine_specific_fields=self.engine_specific_fields
        )

        for schema in schemas:
            schema["SelectFromEntity"] = ".".join(
                [schema["Catalog"], schema["Schema"], schema["Entity"]]
            )

            del schema["Entity"]
            del schema["Schema"]
            del schema["Catalog"]

        if as_json:
            return json.dumps(schemas, default=str)
        else:
            return schemas
