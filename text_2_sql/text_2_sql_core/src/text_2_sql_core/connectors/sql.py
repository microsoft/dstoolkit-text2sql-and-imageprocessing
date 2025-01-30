# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import os
from typing import Annotated, Union
from text_2_sql_core.connectors.factory import ConnectorFactory
import asyncio
import sqlglot
from sqlglot.expressions import Parameter, Select, Identifier
from abc import ABC, abstractmethod
from jinja2 import Template
import json
from text_2_sql_core.utils.database import DatabaseEngineSpecificFields


class SqlConnector(ABC):
    def __init__(self):
        # Feature flags from environment variables
        self.use_query_cache = (
            os.environ.get("Text2Sql__UseQueryCache", "True").lower() == "true"
        )
        self.pre_run_query_cache = (
            os.environ.get("Text2Sql__PreRunQueryCache", "True").lower() == "true"
        )
        self.use_column_value_store = (
            os.environ.get("Text2Sql__UseColumnValueStore", "True").lower() == "true"
        )
        self.use_ai_search = (
            os.environ.get("Text2Sql__UseAISearch", "True").lower() == "true"
        )

        # Only initialize AI Search connector if enabled
        self.ai_search_connector = (
            ConnectorFactory.get_ai_search_connector() if self.use_ai_search else None
        )

        self.database_engine = None

    @property
    @abstractmethod
    def engine_specific_rules(self) -> str:
        """Get the engine specific rules."""
        pass

    @property
    @abstractmethod
    def invalid_identifiers(self) -> list[str]:
        """Get the invalid identifiers upon which a sql query is rejected."""
        pass

    @property
    @abstractmethod
    def engine_specific_fields(self) -> list[str]:
        """Get the engine specific fields."""
        pass

    @property
    def excluded_engine_specific_fields(self):
        """A method to get the excluded fields for the database engine."""

        return [
            field.value.capitalize()
            for field in DatabaseEngineSpecificFields
            if field not in self.engine_specific_fields
        ]

    @abstractmethod
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

    async def get_column_values(
        self,
        text: Annotated[
            str,
            "The text to run a semantic search against. Relevant entities will be returned.",
        ],
        as_json: bool = True,
    ):
        """Gets the values of a column in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
        -------
            str: The values of the column in JSON format.
        """
        # Return empty results if AI Search is disabled
        if not self.use_ai_search:
            filter_to_column = {text: {}}
            return (
                json.dumps(filter_to_column, default=str)
                if as_json
                else filter_to_column
            )

        values = await self.ai_search_connector.get_column_values(text)

        # build into a common format
        column_values = {}

        starting = len(self.engine_specific_fields)

        for value in values:
            trimmed_fqn = ".".join(value["FQN"].split(".")[starting:-1])
            if trimmed_fqn not in column_values:
                column_values[trimmed_fqn] = []

            column_values[trimmed_fqn].append(value["Value"])

        logging.info("Column Values: %s", column_values)

        filter_to_column = {text: column_values}

        if as_json:
            return json.dumps(filter_to_column, default=str)
        else:
            return filter_to_column

    @abstractmethod
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

    async def query_execution_with_limit(
        self,
        sql_query: Annotated[
            str,
            "The SQL query to run against the database.",
        ],
    ) -> str:
        """Run the SQL query against the database with a limit of 10 rows.

        Args:
        ----
            sql_query (str): The SQL query to run against the database.

        Returns:
        -------
            str: JSON string containing the query results or error information.
        """
        # Clean the query
        sql_query = sql_query.strip()
        if sql_query.endswith(';'):
            sql_query = sql_query[:-1]
        
        # Validate the SQL query
        validation_result = await self.query_validation(sql_query)

        if isinstance(validation_result, bool) and validation_result:
            try:
                # Execute the query
                result = await self.query_execution(sql_query, cast_to=None, limit=25)
                
                # Return successful result
                return json.dumps({
                    "type": "query_execution_with_limit",
                    "sql_query": sql_query,
                    "sql_rows": result,
                },
                default=str,
            )
            except Exception as e:
                logging.error(f"Query execution error: {e}")
                # Return error result
                return json.dumps({
                    "type": "errored_query_execution_with_limit",
                    "sql_query": sql_query,
                    "errors": str(e),
                },
                default=str,
            )
        else:
            # Return validation error
            return json.dumps({
                "type": "errored_query_execution_with_limit",
                "sql_query": sql_query,
                "errors": validation_result,
            },
            default=str,
        )

    async def query_validation(
        self,
        sql_query: Annotated[
            str,
            "The SQL query to run against the database.",
        ],
    ) -> Union[bool | list[dict]]:
        """Validate the SQL query."""
        try:
            logging.info("Validating SQL Query: %s", sql_query)
            parsed_queries = sqlglot.parse(
                sql_query,
                read=self.database_engine.value.lower(),
            )

            expressions = []
            identifiers = []

            def handle_node(node):
                if isinstance(node, Select):
                    # Extract expressions
                    for expr in node.expressions:
                        expressions.append(expr)
                elif isinstance(node, Identifier):
                    # Extract identifiers
                    identifiers.append(node.this)

            detected_invalid_identifiers = []

            for parsed_query in parsed_queries:
                for node in parsed_query.walk():
                    handle_node(node)

            for token in expressions + identifiers:
                if isinstance(token, Parameter):
                    identifier = str(token.this.this).upper()
                else:
                    identifier = str(token).strip("()").upper()

                if identifier in self.invalid_identifiers:
                    logging.warning("Detected invalid identifier: %s", identifier)
                    detected_invalid_identifiers.append(identifier)

            if len(detected_invalid_identifiers) > 0:
                logging.error(
                    "SQL Query contains invalid identifiers: %s",
                    detected_invalid_identifiers,
                )
                return (
                    "SQL Query contains invalid identifiers: %s"
                    % detected_invalid_identifiers
                )

        except sqlglot.errors.ParseError as e:
            logging.error("SQL Query is invalid: %s", e.errors)
            return e.errors
        else:
            logging.info("SQL Query is valid.")
            return True

    async def fetch_sql_queries_with_schemas_from_cache(
        self, question: str, injected_parameters: dict = None
    ) -> str:
        """Fetch the queries from the cache based on the question.

        Args:
        ----
            question (str): The question to use to fetch the queries.

        Returns:
        -------
            str: The formatted string of the queries fetched from the cache. This is injected into the prompt.
        """
        # Return empty results if AI Search is disabled
        if not self.use_ai_search:
            return {
                "contains_cached_sql_queries_with_schemas_from_cache_database_results": False,
                "cached_sql_queries_with_schemas_from_cache": None,
            }

        if injected_parameters is None:
            injected_parameters = {}

        sql_queries_with_schemas = await self.ai_search_connector.run_ai_search_query(
            question,
            ["QuestionEmbedding"],
            ["Question", "SqlQueryDecomposition"],
            os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"],
            None,
            top=1,
            include_scores=True,
            minimum_score=1.5,
        )

        if len(sql_queries_with_schemas) == 0:
            return {
                "contains_cached_sql_queries_with_schemas_from_cache_database_results": False,
                "cached_sql_queries_with_schemas_from_cache": None,
            }

        # loop through all sql queries and populate the template in place
        for queries_with_schemas in sql_queries_with_schemas:
            for sql_query in queries_with_schemas["SqlQueryDecomposition"]:
                sql_query["SqlQuery"] = Template(sql_query["SqlQuery"]).render(
                    **injected_parameters
                )

        logging.info("Cached SQL Queries with Schemas: %s", sql_queries_with_schemas)
        if self.pre_run_query_cache and len(sql_queries_with_schemas) > 0:
            # check the score
            if sql_queries_with_schemas[0]["@search.reranker_score"] > 2.75:
                logging.info("Score is greater than 3")

                query_result_store = {}

                query_tasks = []

                for sql_query in sql_queries_with_schemas[0]["SqlQueryDecomposition"]:
                    logging.info("SQL Query: %s", sql_query)

                    # Run the SQL query
                    query_tasks.append(self.query_execution(sql_query["SqlQuery"]))

                sql_results = await asyncio.gather(*query_tasks)

                for sql_query, sql_result in zip(
                    sql_queries_with_schemas[0]["SqlQueryDecomposition"], sql_results
                ):
                    query_result_store[sql_query["SqlQuery"]] = {
                        "sql_rows": sql_result,
                        "schemas": sql_query["Schemas"],
                    }

                return {
                    "contains_cached_sql_queries_with_schemas_from_cache_database_results": True,
                    "cached_sql_queries_with_schemas_from_cache": query_result_store,
                }

        return {
            "contains_cached_sql_queries_with_schemas_from_cache_database_results": False,
            "cached_sql_queries_with_schemas_from_cache": sql_queries_with_schemas,
        }
