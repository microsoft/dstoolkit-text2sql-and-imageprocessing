import logging
import os
import aioodbc


async def sql_query_execution(sql_query: str) -> list[dict]:
    """Run the SQL query against the database.

    Args:
    ----
        sql_query (str): The SQL query to run against the database.

    Returns:
    -------
        list[dict]: The results of the SQL query.
    """
    connection_string = os.environ["Text2Sql__DatabaseConnectionString"]
    async with await aioodbc.connect(dsn=connection_string) as sql_db_client:
        async with sql_db_client.cursor() as cursor:
            await cursor.execute(sql_query)

            columns = [column[0] for column in cursor.description]

            rows = await cursor.fetchall()
            results = [dict(zip(columns, returned_row)) for returned_row in rows]

    logging.debug("Results: %s", results)
    return results
