# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from semantic_kernel.functions import kernel_function
from typing import Annotated
import os
import json
import logging
from text_2_sql_core.connectors.ai_search import AISearchConnector
import asyncio
import aioodbc


class VectorBasedSQLPlugin:
    """A plugin that allows for the execution of SQL queries against a SQL Database.

    This is an improved version of the SQLPlugin that uses a vector-based approach to generate SQL queries. This works best for a database with a large number of entities and columns.
    """

    def __init__(self, target_engine: str = "Microsoft TSQL Server"):
        """Initialize the SQL Plugin.

        Args:
        ----
            target_engine (str): The target database engine to run the queries against. Default is 'SQL Server'.
        """
        self.entities = {}
        self.target_engine = target_engine
        self.schemas = {}
        self.question = None

        self.use_query_cache = False
        self.pre_run_query_cache = False

        self.set_mode()

        self.ai_search = AISearchConnector()

    def set_mode(self):
        """Set the mode of the plugin based on the environment variables."""
        self.use_query_cache = (
            os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true"
        )

        self.pre_run_query_cache = (
            os.environ.get("Text2Sql__PreRunQueryCache", "False").lower() == "true"
        )

    def filter_schemas_against_statement(self, sql_statement: str) -> list[dict]:
        """Filter the schemas against the SQL statement to find the matching entities.

        Args:
        ----
            sql_statement (str): The SQL statement to filter the schemas against.

        Returns:
        -------
            list[dict]: The list of matching entities."""
        matching_entities = []

        logging.info("SQL Statement: %s", sql_statement)
        logging.info("Filtering schemas against SQL statement")

        # Convert SQL statement to lowercase for case-insensitive matching
        sql_statement_lower = sql_statement.lower()

        # Iterate over each schema in the list
        for schema in self.schemas.values():
            logging.info("Schema: %s", schema)
            entity = schema["Entity"]
            database = os.environ["Text2Sql__DatabaseName"]
            select_from_entity = f"{database}.{entity}"

            logging.info("Entity: %s", select_from_entity)
            if select_from_entity.lower() in sql_statement_lower:
                matching_entities.append(schema)

        return matching_entities

    async def query_execution(self, sql_query: str) -> list[dict]:
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

    async def fetch_schemas_from_store(self, search: str) -> list[dict]:
        """Fetch the schemas from the store based on the search term.

        Args:
        ----
            search (str): The search term to use to fetch the schemas.

        Returns:
        -------
            list[dict]: The list of schemas fetched from the store."""
        schemas = await self.ai_search.run_ai_search_query(
            search,
            ["DefinitionEmbedding"],
            [
                "Entity",
                "EntityName",
                "Definition",
                "Columns",
                "EntityRelationships",
                "CompleteEntityRelationshipsGraph",
            ],
            os.environ["AIService__AzureSearchOptions__Text2SqlSchemaStore__Index"],
            os.environ[
                "AIService__AzureSearchOptions__Text2SqlSchemaStore__SemanticConfig"
            ],
            top=3,
        )

        for schema in schemas:
            entity = schema["Entity"]
            database = os.environ["Text2Sql__DatabaseName"]
            schema["SelectFromEntity"] = f"{database}.{entity}"

            self.schemas[entity] = schema

        return schemas

    async def fetch_sql_queries_with_schemas_from_cache(self, question: str) -> str:
        """Fetch the queries from the cache based on the question.

        Args:
        ----
            question (str): The question to use to fetch the queries.

        Returns:
        -------
            str: The formatted string of the queries fetched from the cache. This is injected into the prompt.
        """
        if not self.use_query_cache:
            return None

        sql_queries_with_schemas = await self.ai_search.run_ai_search_query(
            question,
            ["QuestionEmbedding"],
            ["Question", "SqlQueryDecomposition"],
            os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"],
            os.environ[
                "AIService__AzureSearchOptions__Text2SqlQueryCache__SemanticConfig"
            ],
            top=1,
            include_scores=True,
            minimum_score=1.5,
        )

        if len(sql_queries_with_schemas) == 0:
            return None
        else:
            database = os.environ["Text2Sql__DatabaseName"]
            for entry in sql_queries_with_schemas["SqlQueryDecomposition"]:
                for schema in entry["Schemas"]:
                    entity = schema["Entity"]
                    schema["SelectFromEntity"] = f"{database}.{entity}"

                    self.schemas[entity] = schema

        pre_fetched_results_string = ""
        if self.pre_run_query_cache and len(sql_queries_with_schemas) > 0:
            logging.info(
                "Cached SQL Queries with Schemas: %s", sql_queries_with_schemas
            )

            # check the score
            if sql_queries_with_schemas[0]["@search.reranker_score"] > 2.75:
                logging.info("Score is greater than 3")

                sql_queries = sql_queries_with_schemas[0]["SqlQueryDecomposition"]
                query_result_store = {}

                query_tasks = []

                for sql_query in sql_queries:
                    logging.info("SQL Query: %s", sql_query)

                    # Run the SQL query
                    query_tasks.append(self.query_execution(sql_query["SqlQuery"]))

                sql_results = await asyncio.gather(*query_tasks)

                for sql_query, sql_result in zip(sql_queries, sql_results):
                    query_result_store[sql_query["SqlQuery"]] = {
                        "result": sql_result,
                        "schemas": sql_query["Schemas"],
                    }

                pre_fetched_results_string = f"""[BEGIN PRE-FETCHED RESULTS FOR CACHED SQL QUERIES]\n{
                    json.dumps(query_result_store, default=str)}\n[END PRE-FETCHED RESULTS FOR CACHED SQL QUERIES]\n"""

                return pre_fetched_results_string

        formatted_sql_cache_string = f"""[BEGIN CACHED QUERIES AND SCHEMAS]:\n{
            json.dumps(sql_queries_with_schemas, default=str)}[END CACHED QUERIES AND SCHEMAS]"""

        return formatted_sql_cache_string

    async def sql_prompt_injection(
        self, engine_specific_rules: str | None = None, question: str | None = None
    ) -> str:
        """Get the schemas for the database entities and provide a system prompt for the user.

        Returns:
            str: The system prompt for the user.
        """

        self.question = question

        if engine_specific_rules:
            engine_specific_rules = f"""\n        The following {
                self.target_engine} Syntax rules must be adhered to.\n        {engine_specific_rules}"""

        self.set_mode()

        if self.use_query_cache:
            query_cache_string = await self.fetch_sql_queries_with_schemas_from_cache(
                question
            )
        else:
            query_cache_string = None

        if query_cache_string is not None and (
            self.use_query_cache and not self.pre_run_query_cache
        ):
            query_prompt = f"""First look at the provided CACHED QUERIES AND SCHEMAS below, to see if you can use them to formulate a SQL query.

            {query_cache_string}

            If you can't the above or adjust a previous generated SQL query, use the 'GetEntitySchema()' function to search for the most relevant schemas for the data that you wish to obtain.
            """
        elif query_cache_string is not None and (
            self.use_query_cache and self.pre_run_query_cache
        ):
            query_prompt = f"""First consider the PRE-FETCHED SQL query and the results from execution. Consider if you can use this data to answer the question without running another SQL query. If the data is sufficient, use it to answer the question instead of running a new query.

            {query_cache_string}

            Finally, if you can't use or adjust a previous generated SQL query, use the 'GetEntitySchema()' function to search for the most relevant schemas for the data that you wish to obtain."""
        else:
            schemas_string = await self.fetch_schemas_from_store(question)
            formatted_schemas_string = f"""[BEGIN SELECTED SCHEMAS]:\n{
                json.dumps(schemas_string, default=str)}[END SELECTED SCHEMAS]"""
            query_prompt = f"""
            First look at the SELECTED SCHEMAS below which have been retrieved based on the user question. Consider if you can use these schemas to formulate a SQL query.

            {formatted_schemas_string}

            Check the above schemas carefully to see if they can be used to formulate a SQL query. If you need additional schemas, use 'GetEntitySchema()' function to search for the most relevant schemas for the data that you wish to obtain."""

        sql_prompt_injection = f"""{query_prompt}

        If needed, use the 'RunSQLQuery()' function to run the SQL query against the database. Never just return the SQL query as the answer.

        Output corresponding text values in the answer for columns where there is an ID. For example, if the column is 'ProductID', output the corresponding 'ProductModel' in the response. Do not include the ID in the response.
        If a user is asking for a comparison, always compare the relevant values in the database.

        Only use schema / column information provided as part of this prompt or from the 'GetEntitySchema()' function output when constructing a SQL query. Do not use any other entities and columns in your SQL query, other than those defined above.
        Do not makeup or guess column names.

        The target database engine is {self.target_engine}, SQL queries must be able compatible to run on {self.target_engine}. {engine_specific_rules}
        You must only provide SELECT SQL queries.
        For a given entity, use the 'SelectFromEntity' property returned in the schema in the SELECT FROM part of the SQL query. If the property is {{'SelectFromEntity': 'test_schema.test_table'}}, the select statement will be formulated from 'SELECT <VALUES> FROM test_schema.test_table WHERE <CONDITION>.

        If you don't know how the value is formatted in a column, run a query against the column to get the unique values that might match your query.
        Some columns in the schema may have the properties 'AllowedValues' or 'SampleValues'. Use these values to determine the possible values that can be used in the SQL query.

        The source title to cite is the 'EntityName' property. The source reference is the SQL query used. The source chunk is the result of the SQL query used to answer the user query in Markdown table format. e.g. {{ 'title': "vProductAndDescription", 'chunk': '| ProductID | Name              | ProductModel | Culture | Description                      |\\n|-----------|-------------------|--------------|---------|----------------------------------|\\n| 101       | Mountain Bike     | MT-100       | en      | A durable bike for mountain use. |\\n| 102       | Road Bike         | RB-200       | en      | Lightweight bike for road use.   |\\n| 103       | Hybrid Bike       | HB-300       | fr      | Vélo hybride pour usage mixte.   |\\n', 'reference': 'SELECT ProductID, Name, ProductModel, Culture, Description FROM vProductAndDescription WHERE Culture = \"en\";' }}"""

        return sql_prompt_injection

    @kernel_function(
        description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Extract key terms from the user question and use these as the search term. Several entities may be returned. Only use when the provided schemas in the system prompt are not sufficient to answer the question.",
        name="GetEntitySchema",
    )
    async def get_entity_schemas(
        self,
        text: Annotated[
            str,
            "The text to run a semantic search against. Relevant entities will be returned.",
        ],
    ) -> str:
        """Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
            str: The schema of the views or tables in JSON format.
        """

        schemas = await self.fetch_schemas_from_store(text)
        return json.dumps(schemas, default=str)

    @kernel_function(
        description="Runs an SQL query against the SQL Database to extract information.",
        name="RunSQLQuery",
    )
    async def run_sql_query(
        self,
        sql_query: Annotated[str, "The SQL query to run against the DB"],
    ) -> str:
        """Sends an SQL Query to the SQL Databases and returns to the result.

        Args:
        ----
            sql_query (str): The query to run against the DB.

        Returns:
            str: The JSON representation of the query results."""

        logging.info("Executing SQL Query")
        logging.debug("SQL Query: %s", sql_query)

        results = await self.query_execution(sql_query)

        if self.use_query_cache and self.question is not None:
            entry = None
            try:
                cleaned_schemas = []

                matching_schemas = self.filter_schemas_against_statement(sql_query)

                if len(matching_schemas) == 0:
                    return json.dumps(results, default=str)

                for schema in matching_schemas:
                    logging.info("Loaded Schema: %s", schema)
                    valid_columns = ["Entity", "Columns"]

                    cleaned_schema = {}
                    for valid_column in valid_columns:
                        cleaned_schema[valid_column] = schema[valid_column]

                    cleaned_schemas.append(cleaned_schema)

                entry = {
                    "Question": self.question,
                    "SqlQueryDecomposition": [
                        {
                            "SqlQuery": sql_query,
                            "Schemas": cleaned_schemas,
                        }
                    ],
                }
            except Exception as e:
                logging.error("Error: %s", e)
                raise e
            else:
                if entry is not None:
                    task = self.ai_search.add_entry_to_index(
                        entry,
                        {"Question": "QuestionEmbedding"},
                        os.environ[
                            "AIService__AzureSearchOptions__Text2SqlQueryCache__Index"
                        ],
                    )

                asyncio.create_task(task)

        return json.dumps(results, default=str)
