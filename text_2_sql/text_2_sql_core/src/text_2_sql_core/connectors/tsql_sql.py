# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
import aioodbc
from typing import Annotated
import os
import logging


class TSQLSqlConnector(SqlConnector):
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
        connection_string = os.environ["Text2Sql__DatabaseConnectionString"]
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
