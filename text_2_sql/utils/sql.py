# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import aioodbc
import os
import logging
from utils.ai_search import add_entry_to_index, run_ai_search_query
import json


async def run_sql_query(sql_query: str) -> list[dict]:
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


async def add_queries_to_cache(question: str, response: dict):
    """Add the queries to the cache.

    Args:
    ----
        response (dict): The response from the AI model.
    """
    # Add the queries to the cache
    queries = [source["reference"] for source in response["sources"]]

    for query in queries:
        entry = {"Question": question, "Query": query, "Schemas": response["schemas"]}
        await add_entry_to_index(
            entry,
            {"Question": "QuestionEmbedding"},
            os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"],
        )


async def fetch_queries_from_cache(question: str):
    use_query_cache = (
        os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true"
    )

    if not use_query_cache:
        return ""

    cached_schemas = await run_ai_search_query(
        question,
        ["QuestionEmbedding"],
        ["Question", "Query", "Schemas"],
        os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"],
        os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__SemanticConfig"],
        top=3,
        include_scores=True,
    )

    pre_run_query_cache = (
        os.environ.get("Text2Sql__PreRunQueryCache", "False").lower() == "true"
    )

    pre_computed_match = ""
    if pre_run_query_cache and len(cached_schemas) > 0:
        logging.info("Cached schemas: %s", cached_schemas)

        # check the score
        if cached_schemas[0]["@search.reranker_score"] > 2.75:
            logging.info("Score is greater than 3")

            sql_query = cached_schemas[0]["Query"]

            logging.info("SQL Query: %s", sql_query)

            # Run the SQL query
            sql_result = await run_sql_query(sql_query)
            logging.info("SQL Query Result: %s", sql_result)

            pre_computed_match = f"Pre-run SQL result from the cache using query '{sql_query}':\n{json.dumps(sql_result, default=str)}\n"

    formatted_sql_cache_string = f"""{pre_computed_match}Top 3 matching questions and schemas:
    {json.dumps(cached_schemas, default=str)}
    """

    return formatted_sql_cache_string
