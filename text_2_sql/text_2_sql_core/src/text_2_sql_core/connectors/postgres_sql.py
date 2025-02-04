# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
import psycopg
from typing import Annotated
import os
import logging
import json
from urllib.parse import urlparse
from text_2_sql_core.utils.database import DatabaseEngine, DatabaseEngineSpecificFields


class PostgresSqlConnector(SqlConnector):
    def __init__(self):
        super().__init__()

        self.database_engine = DatabaseEngine.POSTGRES

    @property
    def engine_specific_rules(self) -> str:
        """Get the engine specific rules."""
        return ""

    @property
    def engine_specific_fields(self) -> list[str]:
        """Get the engine specific fields."""
        return [DatabaseEngineSpecificFields.DATABASE]

    @property
    def invalid_identifiers(self) -> list[str]:
        """Get the invalid identifiers upon which a sql query is rejected."""

        return [
            "CURRENT_USER",  # Returns the name of the current user
            "SESSION_USER",  # Returns the name of the user that initiated the session
            "USER",  # Returns the name of the current user
            "CURRENT_ROLE",  # Returns the current role
            "CURRENT_DATABASE",  # Returns the name of the current database
            "CURRENT_SCHEMA()",  # Returns the name of the current schema
            "CURRENT_SETTING()",  # Returns the value of a specified configuration parameter
            "PG_CURRENT_XACT_ID()",  # Returns the current transaction ID
            # (if the extension is enabled) Provides a view of query statistics
            "PG_STAT_STATEMENTS()",
            "PG_SLEEP()",  # Delays execution by the specified number of seconds
            "CLIENT_ADDR()",  # Returns the IP address of the client (from pg_stat_activity)
            "CLIENT_HOSTNAME()",  # Returns the hostname of the client (from pg_stat_activity)
            "PGP_SYM_DECRYPT()",  # (from pgcrypto extension) Symmetric decryption function
            "PGP_PUB_DECRYPT()",  # (from pgcrypto extension) Asymmetric decryption function
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
        sql_query: Annotated[str, "The SQL query to run against the database."],
        cast_to: any = None,
        limit=None,
    ) -> list[dict]:
        """Run the SQL query against the Postgres database asynchronously.

        Args:
        ----
            sql_query (str): The SQL query to run against the database.

        Returns:
        -------
            list[dict]: The results of the SQL query.
        """
        logging.info(f"Running query: {sql_query}")
        results = []

        if "Text2Sql__Postgres__ConnectionString" in os.environ:
            logging.info("Postgres Connection string found in environment variables.")

            p = urlparse(os.environ["Text2Sql__Postgres__ConnectionString"])

            postgres_connections = {
                "dbname": p.path[1:],
                "user": p.username,
                "password": p.password,
                "port": p.port,
                "host": p.hostname,
            }
        else:
            logging.warning(
                "Postgres Connection string not found in environment variables. Using individual variables."
            )
            postgres_connections = {
                "dbname": os.environ["Text2Sql__Postgres__Database"],
                "user": os.environ["Text2Sql__Postgres__User"],
                "password": os.environ["Text2Sql__Postgres__Password"],
                "port": os.environ["Text2Sql__Postgres__Port"],
                "host": os.environ["Text2Sql__Postgres__ServerHostname"],
            }

        # Establish an asynchronous connection to the Postgres database
        async with await psycopg.AsyncConnection.connect(
            **postgres_connections
        ) as conn:
            # Create an asynchronous cursor
            async with conn.cursor() as cursor:
                await cursor.execute(sql_query)

                # Fetch column names
                columns = [column[0] for column in cursor.description]

                # Fetch rows based on the limit
                if limit is not None:
                    rows = await cursor.fetchmany(limit)
                else:
                    rows = await cursor.fetchall()

                # Process the rows
                for row in rows:
                    if cast_to:
                        results.append(cast_to.from_sql_row(row, columns))
                    else:
                        results.append(dict(zip(columns, row)))

        logging.debug("Results: %s", results)
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
            schema["SelectFromEntity"] = ".".join([schema["Schema"], schema["Entity"]])

            del schema["Entity"]
            del schema["Schema"]
            del schema["Database"]

        if as_json:
            return json.dumps(schemas, default=str)
        else:
            return schemas
