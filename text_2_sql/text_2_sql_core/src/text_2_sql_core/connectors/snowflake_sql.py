# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
import snowflake.connector
from typing import Annotated
import asyncio
import os
import logging
import json

from text_2_sql_core.utils.database import DatabaseEngine, DatabaseEngineSpecificFields


class SnowflakeSqlConnector(SqlConnector):
    def __init__(self):
        super().__init__()

        self.database_engine = DatabaseEngine.SNOWFLAKE

    @property
    def engine_specific_rules(self) -> str:
        """Get the engine specific rules."""
        return """When an ORDER BY clause is included in the SQL query, always append the ORDER BY clause with 'NULLS LAST' to ensure that NULL values are at the end of the result set. e.g. 'ORDER BY column_name DESC NULLS LAST'."""

    @property
    def engine_specific_fields(self) -> list[str]:
        """Get the engine specific fields."""
        return [
            DatabaseEngineSpecificFields.WAREHOUSE,
            DatabaseEngineSpecificFields.DATABASE,
        ]

    @property
    def invalid_identifiers(self) -> list[str]:
        """Get the invalid identifiers upon which a sql query is rejected."""
        return [
            "CURRENT_CLIENT",
            "CURRENT_IP_ADDRESS",
            "CURRENT_REGION",
            "CURRENT_VERSION",
            "ALL_USER_NAMES",
            "CURRENT_ACCOUNT",
            "CURRENT_ACCOUNT_NAME",
            "CURRENT_ORGANIZATION_NAME",
            "CURRENT_ROLE",
            "CURRENT_AVAILABLE_ROLES",
            "CURRENT_SECONDARY_ROLES",
            "CURRENT_SESSION",
            "CURRENT_STATEMENT",
            "CURRENT_TRANSACTION",
            "CURRENT_USER",
            "GETVARIABLE",
            "LAST_QUERY_ID",
            "LAST_TRANSACTION",
            "CURRENT_DATABASE",
            "CURRENT_ROLE_TYPE",
            "CURRENT_SCHEMA",
            "CURRENT_SCHEMAS",
            "CURRENT_WAREHOUSE",
            "INVOKER_ROLE",
            "INVOKER_SHARE",
            "IS_APPLICATION_ROLE_IN_SESSION",
            "IS_DATABASE_ROLE_IN_SESSION",
            "IS_GRANTED_TO_INVOKER_ROLE",
            "IS_INSTANCE_ROLE_IN_SESSION",
            "IS_ROLE_IN_SESSION",
            "POLICY_CONTEXT",
            "CURRENT_SESSION_USER",
            "SESSION_ID",
            "QUERY_START_TIME",
            "QUERY_ELAPSED_TIME",
            "QUERY_MEMORY_USAGE",
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
        return f'"{identifier}"'

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

        # Create a connection to Snowflake, without specifying a schema
        conn = snowflake.connector.connect(
            user=os.environ["Text2Sql__Snowflake__User"],
            password=os.environ["Text2Sql__Snowflake__Password"],
            account=os.environ["Text2Sql__Snowflake__Account"],
            warehouse=os.environ["Text2Sql__Snowflake__Warehouse"],
            database=os.environ["Text2Sql__Snowflake__Database"],
        )

        try:
            # Using the connection to create a cursor
            cursor = conn.cursor()

            # Execute the query
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
                if cast_to:
                    results.append(cast_to.from_sql_row(row, columns))
                else:
                    results.append(dict(zip(columns, row)))

        finally:
            cursor.close()
            conn.close()

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
                [
                    schema["Warehouse"],
                    schema["Database"],
                    schema["Schema"],
                    schema["Entity"],
                ]
            )

            del schema["Entity"]
            del schema["Schema"]
            del schema["Warehouse"]
            del schema["Database"]

        if as_json:
            return json.dumps(schemas, default=str)
        else:
            return schemas
