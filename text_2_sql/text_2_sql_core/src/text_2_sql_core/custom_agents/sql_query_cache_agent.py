# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.factory import ConnectorFactory
import logging


class SqlQueryCacheAgentCustomAgent:
    def __init__(self):
        self.sql_connector = ConnectorFactory.get_database_connector()

    async def process_message(self, message: str, injected_parameters: dict) -> dict:
        # Initialize results dictionary
        cached_results = {
            "cached_sql_queries_with_schemas_from_cache": [],
            "contains_cached_sql_queries_with_schemas_from_cache_database_results": False,
        }

        # Fetch the queries from the cache based on the question
        logging.info(f"Fetching queries from cache for question: {message}")
        cached_query = (
            await self.sql_connector.fetch_sql_queries_with_schemas_from_cache(
                message, injected_parameters=injected_parameters
            )
        )

        # If any question has pre-run results, set the flag
        if cached_query.get(
            "contains_cached_sql_queries_with_schemas_from_cache_database_results",
            False,
        ):
            cached_results[
                "contains_cached_sql_queries_with_schemas_from_cache_database_results"
            ] = True

        # Add the cached results for this question
        if cached_query.get("cached_sql_queries_with_schemas_from_cache"):
            cached_results["cached_sql_queries_with_schemas_from_cache"].extend(
                cached_query["cached_sql_queries_with_schemas_from_cache"]
            )

        logging.info(f"Final cached results: {cached_results}")
        return cached_results
