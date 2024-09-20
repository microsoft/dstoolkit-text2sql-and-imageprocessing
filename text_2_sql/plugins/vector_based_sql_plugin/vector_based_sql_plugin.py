# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from semantic_kernel.functions import kernel_function
from typing import Annotated
import os
import json
import logging
from utils.ai_search import run_ai_search_query, add_entry_to_index
from utils.sql import run_sql_query
import asyncio


class VectorBasedSQLPlugin:
    """A plugin that allows for the execution of SQL queries against a SQL Database.

    This is an improved version of the SQLPlugin that uses a vector-based approach to generate SQL queries. This works best for a database with a large number of entities and columns.
    """

    def __init__(self, database: str, target_engine: str = "Microsoft TSQL Server"):
        """Initialize the SQL Plugin.

        Args:
        ----
            database (str): The name of the database to connect to.
            target_engine (str): The target database engine to run the queries against. Default is 'SQL Server'.
        """
        self.entities = {}
        self.database = database
        self.target_engine = target_engine

    def system_prompt(self, engine_specific_rules: str | None = None) -> str:
        """Get the schemas for the database entities and provide a system prompt for the user.

        Returns:
            str: The system prompt for the user.
        """

        if engine_specific_rules:
            engine_specific_rules = f"""\n        The following {
                self.target_engine} Syntax rules must be adhered to.\n        {engine_specific_rules}"""

        use_query_cache = (
            os.environ.get("Text2Sql__UseQueryCache", "False").lower() == "true"
        )

        pre_run_query_cache = (
            os.environ.get("Text2Sql__PreRunQueryCache", "False").lower() == "true"
        )

        if use_query_cache and not pre_run_query_cache:
            query_prompt = """First look at the provided cached queries, and associated schemas to see if you can use them to formulate a SQL query. If you can't use or adjust a previous generated SQL query, use the 'GetEntitySchema()' function to search for the most relevant schemas for the data that you wish to obtain.
            """
        elif use_query_cache and pre_run_query_cache:
            query_prompt = """First consider the pre-fetched SQL query and the results from execution. Consider if you can use this data to answer the question without running another SQL query.

            If this data or query will not answer the question, look at the provided cached queries, and associated schemas to see if you can use them to formulate a SQL query.

            Finally, if you can't use or adjust a previous generated SQL query, use the 'GetEntitySchema()' function to search for the most relevant schemas for the data that you wish to obtain."""
        else:
            query_prompt = """Use the 'GetEntitySchema()' function to search for the most relevant schemas for the data that you wish to obtain.

            Always generate the SQL query based on the GetEntitySchema() function output, do not use the chat history data to generate the SQL query.
            Only use the column names obtained from GetEntitySchema() when constructing a SQL query, do not make up column names."""

        system_prompt = f"""{query_prompt}

        If needed, use the 'RunSQLQuery()' function to run the SQL query against the database. Never just return the SQL query as the answer.

        Output corresponding text values in the answer for columns where there is an ID. For example, if the column is 'ProductID', output the corresponding 'ProductModel' in the response. Do not include the ID in the response.
        If a user is asking for a comparison, always compare the relevant values in the database.

        Only use schema / column information provided as part of [CACHED SCHEMAS] or fetched from GetEntitySchema() to construct the SQL query. Do NOT use any other columns or make up column names.

        The target database engine is {self.target_engine}, SQL queries must be able compatible to run on {self.target_engine}. {engine_specific_rules}
        You must only provide SELECT SQL queries.
        For a given entity, use the 'SelectFromEntity' property returned in the schema in the SELECT FROM part of the SQL query. If the property is {{'SelectFromEntity': 'test_schema.test_table'}}, the select statement will be formulated from 'SELECT <VALUES> FROM test_schema.test_table WHERE <CONDITION>.

        If you don't know how the value is formatted in a column, run a query against the column to get the unique values that might match your query.
        Some columns in the schema may have the properties 'AllowedValues' or 'SampleValues'. Use these values to determine the possible values that can be used in the SQL query.

        The source title to cite is the 'EntityName' property. The source reference is the SQL query used. The source chunk is the result of the SQL query used to answer the user query in Markdown table format. e.g. {{ 'title': "vProductAndDescription", 'chunk': '| ProductID | Name              | ProductModel | Culture | Description                      |\\n|-----------|-------------------|--------------|---------|----------------------------------|\\n| 101       | Mountain Bike     | MT-100       | en      | A durable bike for mountain use. |\\n| 102       | Road Bike         | RB-200       | en      | Lightweight bike for road use.   |\\n| 103       | Hybrid Bike       | HB-300       | fr      | Vélo hybride pour usage mixte.   |\\n', 'reference': 'SELECT ProductID, Name, ProductModel, Culture, Description FROM vProductAndDescription WHERE Culture = \"en\";' }}"""

        return system_prompt

    @kernel_function(
        description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Extract key terms from the user question and use these as the search term. Several entities may be returned.",
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

        schemas = await run_ai_search_query(
            text,
            ["DescriptionEmbedding"],
            ["Entity", "EntityName", "Description", "Columns"],
            os.environ["AIService__AzureSearchOptions__Text2Sql__Index"],
            os.environ["AIService__AzureSearchOptions__Text2Sql__SemanticConfig"],
            top=3,
        )

        for schema in schemas:
            schema["SelectFromEntity"] = f"{self.database}.{schema['Entity']}"

        return json.dumps(schemas, default=str)

    @kernel_function(
        description="Runs an SQL query against the SQL Database to extract information.",
        name="RunSQLQuery",
    )
    async def run_sql_query(
        self,
        sql_query: Annotated[str, "The SQL query to run against the DB"],
        question: Annotated[
            str, "The question that was asked by the user in unedited form."
        ],
        schemas: Annotated[
            str,
            "JSON string of array schemas that were used to generate the SQL query. This is either the output of GetEntitySchema() or the cached schemas.",
        ],
    ) -> str:
        """Sends an SQL Query to the SQL Databases and returns to the result.

        Args:
        ----
            sql_query (str): The query to run against the DB.

        Returns:
            str: The JSON representation of the query results."""

        logging.info("Executing SQL Query")
        logging.debug("SQL Query: %s", sql_query)

        results = await run_sql_query(sql_query)

        entry = {
            "Question": question,
            "Query": sql_query,
            "Schemas": json.loads(schemas),
        }
        task = add_entry_to_index(
            entry,
            {"Question": "QuestionEmbedding"},
            os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"],
        )

        asyncio.create_task(task)

        return json.dumps(results, default=str)
