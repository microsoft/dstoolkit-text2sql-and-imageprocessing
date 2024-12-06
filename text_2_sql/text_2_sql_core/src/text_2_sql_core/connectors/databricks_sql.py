# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.sql import SqlConnector
from databricks import sql
from typing import Annotated
import asyncio
import os
import logging


class DatabricksSqlConnector(SqlConnector):
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
