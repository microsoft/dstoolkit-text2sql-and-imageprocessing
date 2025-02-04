# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
import aioodbc
from typing import Annotated
import os
import logging
import json

from text_2_sql_core.utils.database import DatabaseEngine, DatabaseEngineSpecificFields


class TsqlSqlConnector(SqlConnector):
    def __init__(self):
        super().__init__()

        self.database_engine = DatabaseEngine.TSQL

    @property
    def engine_specific_rules(self) -> str:
        """Get the engine specific rules."""
        return """Use TOP X instead of LIMIT X to limit the number of rows returned."""

    @property
    def engine_specific_fields(self) -> list[str]:
        """Get the engine specific fields."""
        return [DatabaseEngineSpecificFields.DATABASE]

    @property
    def invalid_identifiers(self) -> list[str]:
        """Get the invalid identifiers upon which a sql query is rejected."""
        return [
            "CONNECTIONS",
            "CPU_BUSY",
            "CURSOR_ROWS",
            "DATEFIRST",
            "DBTS",
            "ERROR",
            "FETCH_STATUS",
            "IDENTITY",
            "IDLE",
            "IO_BUSY",
            "LANGID",
            "LANGUAGE",
            "LOCK_TIMEOUT",
            "MAX_CONNECTIONS",
            "MAX_PRECISION",
            "NESTLEVEL",
            "OPTIONS",
            "PACK_RECEIVED",
            "PACK_SENT",
            "PACKET_ERRORS",
            "PROCID",
            "REMSERVER",
            "ROWCOUNT",
            "SERVERNAME",
            "SERVICENAME",
            "SPID",
            "TEXTSIZE",
            "TIMETICKS",
            "TOTAL_ERRORS",
            "TOTAL_READ",
            "TOTAL_WRITE",
            "TRANCOUNT",
            "VERSION",
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
        return f"[{identifier}]"

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
        connection_string = os.environ["Text2Sql__Tsql__ConnectionString"]
        async with await aioodbc.connect(dsn=connection_string) as sql_db_client:
            async with sql_db_client.cursor() as cursor:
                await cursor.execute(sql_query)

                columns = [column[0] for column in cursor.description]

                if limit is not None:
                    rows = await cursor.fetchmany(limit)
                else:
                    rows = await cursor.fetchall()
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
