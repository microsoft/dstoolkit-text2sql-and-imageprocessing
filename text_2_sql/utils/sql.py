# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import aioodbc
import os
import logging
from utils.ai_search import run_ai_search_query
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
            results = [dict(zip(columns, returned_row))
                       for returned_row in rows]

    logging.debug("Results: %s", results)
    return results


async def fetch_schemas_from_store(search: str):
    schemas = await run_ai_search_query(
        search,
        ["DescriptionEmbedding"],
        ["Entity", "EntityName", "Description", "Columns"],
        os.environ["AIService__AzureSearchOptions__Text2Sql__Index"],
        os.environ["AIService__AzureSearchOptions__Text2Sql__SemanticConfig"],
        top=3,
    )

    for schema in schemas:
        entity = schema["Entity"]
        database = os.environ["Text2Sql__DatabaseName"]
        schema["SelectFromEntity"] = f"{database}.{entity}"

    return json.dumps(schemas, default=str)


async def fetch_queries_from_cache(question: str):
    use_query_cache = (
        os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true"
    )

    if not use_query_cache:
        return "", ""

    cached_schemas = await run_ai_search_query(
        question,
        ["QuestionEmbedding"],
        ["Question", "Query", "Schemas"],
        os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"],
        os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__SemanticConfig"],
        top=2,
        include_scores=True,
        minimum_score=1.5,
    )

    if len(cached_schemas) == 0:
        return "", ""
    else:
        database = os.environ["Text2Sql__DatabaseName"]
        for entry in cached_schemas:
            for schemas in entry["Schemas"]:
                for schema in schemas:
                    entity = schema["Entity"]
                    schema["SelectFromEntity"] = f"{database}.{entity}"

    pre_run_query_cache = (
        os.environ.get("Text2Sql__PreRunQueryCache", "False").lower() == "true"
    )

    pre_fetched_results_string = ""
    if pre_run_query_cache and len(cached_schemas) > 0:
        logging.info("Cached schemas: %s", cached_schemas)

        # check the score
        if cached_schemas[0]["@search.reranker_score"] > 2.75:
            logging.info("Score is greater than 3")

            sql_query = cached_schemas[0]["Query"]
            schemas = cached_schemas[0]["Schemas"]

            logging.info("SQL Query: %s", sql_query)

            # Run the SQL query
            sql_result = await run_sql_query(sql_query)
            logging.info("SQL Query Result: %s", sql_result)

            pre_fetched_results_string = f"""[BEGIN PRE-FETCHED RESULTS FOR SQL QUERY = '{sql_query}']\n{
                json.dumps(sql_result, default=str)}\nSchema={json.dumps(schemas, default=str)}\n[END PRE-FETCHED RESULTS FOR SQL QUERY]\n"""

            del cached_schemas[0]

    formatted_sql_cache_string = f"""[BEGIN CACHED SCHEMAS]:\n{
        json.dumps(cached_schemas, default=str)}[END CACHED SCHEMAS]"""

    return formatted_sql_cache_string, pre_fetched_results_string
