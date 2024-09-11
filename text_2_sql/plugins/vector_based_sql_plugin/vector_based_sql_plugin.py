# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from semantic_kernel.functions import kernel_function
import aioodbc
from typing import Annotated
import os
import json
import logging
from azure.identity import DefaultAzureCredential
from openai import AsyncAzureOpenAI
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.aio import SearchClient


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
            engine_specific_rules = f"\n        The following {self.target_engine} Syntax rules must be adhered to.\n        {engine_specific_rules}"

        system_prompt = f"""Use the names and descriptions of {self.target_engine} entities provided in ENTITIES LIST to decide which entities to query if you need to retrieve information from the database. Use the 'GetEntitySchema()' function to get more details of the schema of the view you want to query. Use the 'RunSQLQuery()' function to run the SQL query against the database.

        You must always examine the provided {self.target_engine} entity descriptions to determine if they can answer the question.

        Output corresponding text values in the answer for columns where there is an ID. For example, if the column is 'ProductID', output the corresponding 'ProductModel' in the response. Do not include the ID in the response.
        If a user is asking for a comparison, always compare the relevant values in the database.

        The target database engine is {self.target_engine}, SQL queries must be able compatible to run on {self.target_engine}. {engine_specific_rules}
        Always generate the SQL query based on the GetEntitySchema() function output, do not use the chat history data to generate the SQL query.
        Do not use any other entities and columns in your SQL query, other than those defined above. Only use the column names obtained from GetEntitySchema() when constructing a SQL query, do not make up column names.
        You must only provide SELECT SQL queries.
        For a given entity, use the 'SelectFromEntity' property returned from 'GetEntitySchema()' function in the SELECT FROM part of the SQL query. If the property is {{'SelectFromEntity': 'test_schema.test_table'}}, the select statement will be formulated from 'SELECT <VALUES> FROM test_schema.test_table WHERE <CONDITION>.

        If you don't know how the value is formatted in a column, run a query against the column to get the unique values that might match your query.
        Some columns returned from 'GetEntitySchema()' may have the properties 'AllowedValues' or 'SampleValues'. Use these values to determine the possible values that can be used in the SQL query.

        The source title to cite is the 'entity_name' property. The source reference is the SQL query used. The source chunk is the result of the SQL query used to answer the user query in Markdown table format. e.g. {{ 'title': "vProductAndDescription", 'chunk': '| ProductID | Name              | ProductModel | Culture | Description                      |\\n|-----------|-------------------|--------------|---------|----------------------------------|\\n| 101       | Mountain Bike     | MT-100       | en      | A durable bike for mountain use. |\\n| 102       | Road Bike         | RB-200       | en      | Lightweight bike for road use.   |\\n| 103       | Hybrid Bike       | HB-300       | fr      | Vélo hybride pour usage mixte.   |\\n', 'reference': 'SELECT ProductID, Name, ProductModel, Culture, Description FROM vProductAndDescription WHERE Culture = \"en\";' }}"""

        return system_prompt

    @kernel_function(
        description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.",
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

        async with AsyncAzureOpenAI(
            # This is the default and can be omitted
            api_key=os.environ["OpenAI__ApiKey"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            api_version=os.environ["OpenAI__ApiVersion"],
        ) as open_ai_client:
            embeddings = await open_ai_client.embeddings.create(
                model=os.environ["OpenAI__EmbeddingModel"], input=text
            )

            # Extract the embedding vector
            embedding_vector = embeddings.data[0].embedding

        vector_query = VectorizedQuery(
            vector=embedding_vector,
            k_nearest_neighbors=5,
            fields="ChunkEmbedding",
        )

        credential = DefaultAzureCredential()
        async with SearchClient(
            endpoint=os.environ["AIService__AzureSearchOptions__Endpoint"],
            index_name=os.environ["AIService__AzureSearchOptions__Text2Sql__Index"],
            credential=credential,
        ) as search_client:
            results = await search_client.search(
                top=5,
                query_type="semantic",
                semantic_configuration_name=os.environ[
                    "AIService__AzureSearchOptions__Text2Sql__SemanticConfig"
                ],
                search_text=text,
                select="Title,Chunk,SourceUri",
                vector_queries=[vector_query],
            )

            documents = [
                document
                async for result in results.by_page()
                async for document in result
            ]

        logging.debug("Results: %s", documents)
        return json.dumps(documents, default=str)

    @kernel_function(
        description="Runs an SQL query against the SQL Database to extract information.",
        name="RunSQLQuery",
    )
    async def run_sql_query(
        self, sql_query: Annotated[str, "The SQL query to run against the DB"]
    ) -> str:
        """Sends an SQL Query to the SQL Databases and returns to the result.

        Args:
        ----
            sql_query (str): The query to run against the DB.

        Returns:
            str: The JSON representation of the query results."""

        logging.info("Executing SQL Query")
        logging.debug("SQL Query: %s", sql_query)

        connection_string = os.environ["Text2Sql__DatabaseConnectionString"]
        async with await aioodbc.connect(dsn=connection_string) as sql_db_client:
            async with sql_db_client.cursor() as cursor:
                await cursor.execute(sql_query)

                columns = [column[0] for column in cursor.description]

                rows = await cursor.fetchall()
                results = [dict(zip(columns, returned_row)) for returned_row in rows]

        logging.debug("Results: %s", results)

        return json.dumps(results, default=str)
