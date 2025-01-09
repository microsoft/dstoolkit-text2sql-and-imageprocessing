# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.connectors.factory import ConnectorFactory
import logging


class SqlQueryCacheAgentCustomAgent:
    def __init__(self):
        self.sql_connector = ConnectorFactory.get_database_connector()

    async def process_message(
        self, user_inputs: list[str], injected_parameters: dict
    ) -> dict:
        # Initialize results dictionary
        cached_results = {
            "cached_questions_and_schemas": [],
            "contains_pre_run_results": False,
        }

        # Process each question sequentially
        for question in user_inputs:
            # Fetch the queries from the cache based on the question
            logging.info(f"Fetching queries from cache for question: {question}")
            cached_query = await self.sql_connector.fetch_queries_from_cache(
                question, injected_parameters=injected_parameters
            )

            # If any question has pre-run results, set the flag
            if cached_query.get("contains_pre_run_results", False):
                cached_results["contains_pre_run_results"] = True

            # Add the cached results for this question
            if cached_query.get("cached_questions_and_schemas"):
                cached_results["cached_questions_and_schemas"].extend(
                    cached_query["cached_questions_and_schemas"]
                )

        logging.info(f"Final cached results: {cached_results}")
        return cached_results
