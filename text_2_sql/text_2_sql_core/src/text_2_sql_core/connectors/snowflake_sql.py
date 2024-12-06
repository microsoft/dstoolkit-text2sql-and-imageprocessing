# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
import snowflake.connector
from typing import Annotated
import asyncio
import os
import logging


class SnowflakeSqlConnector(SqlConnector):
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
            database=os.environ["Text2Sql__DatabaseName"],
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
