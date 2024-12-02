# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from semantic_kernel.functions import kernel_function
from typing import Annotated
import json
import logging
import os
import aioodbc


class PromptBasedSQLPlugin:
    """A plugin that allows for the execution of SQL queries against a SQL Database."""

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

        self.load_entities()

    def load_entities(self):
        """Load the views from the JSON file and formats into common memory dictionary."""
        with open(
            "../data_dictionary/manual_samples/entities.json", "r", encoding="utf-8"
        ) as file:
            entities = json.load(file)
            for entity_object in entities:
                entity = entity_object["Entity"]
                entity_object["SelectFromEntity"] = f"{self.database}.{entity}"
                entity_name = entity_object["EntityName"].lower()
                self.entities[entity_name] = entity_object

    def sql_prompt_injection(self, engine_specific_rules: str | None = None) -> str:
        """Get the schemas for the database entities and provide a system prompt for the user.

        Returns:
            str: The system prompt for the user.
        """

        entity_descriptions = []
        for entity in self.entities.values():
            entity_string = "     [BEGIN ENTITY = '{}']\n                 Name='{}'\n                 Description='{}'\n             [END ENTITY = '{}']".format(
                entity["EntityName"].upper(),
                entity["EntityName"],
                entity["Description"],
                entity["EntityName"].upper(),
            )
            entity_descriptions.append(entity_string)

        entity_descriptions = "\n\n        ".join(entity_descriptions)

        if engine_specific_rules:
            engine_specific_rules = f"""\n        The following {
                self.target_engine} Syntax rules must be adhered to.\n        {engine_specific_rules}"""

        sql_prompt_injection = f"""Use the names and descriptions of {self.target_engine} entities provided in ENTITIES LIST to decide which entities to query if you need to retrieve information from the database. Use the 'GetEntitySchema()' function to get more details of the schema of the view you want to query.

        Always then use the 'RunSQLQuery()' function to run the SQL query against the database. Never just return the SQL query as the answer.

        Do not give the steps to the user in the response. Make sure to execute the SQL query and return the results in the response.

        You must always examine the provided {self.target_engine} entity descriptions to determine if they can answer the question.

        [BEGIN ENTITIES LIST]
        {entity_descriptions}
        [END ENTITIES LIST]

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

        return sql_prompt_injection

    @kernel_function(
        description="Get the detailed schema of an entity in the Database. Use the entity and the column returned to formulate a SQL query. The view name or table name must be one of the ENTITY NAMES defined in the [ENTITIES LIST]. Only use the column names obtained from GetEntitySchema() when constructing a SQL query, do not make up column names.",
        name="GetEntitySchema",
    )
    async def get_entity_schema(
        self,
        entity_name: Annotated[
            str,
            "The view or table name to get the schema for. It must be one of the ENTITY NAMES defined in the [ENTITIES LIST] function.",
        ],
    ) -> str:
        """Get the schema of a view or table in the SQL Database.

        Args:
        ----
            entity_name (str): A views or table name to get the schema for.

        Returns:
            str: The schema of the views or tables in JSON format.
        """

        if entity_name.lower() not in self.entities:
            return json.dumps(
                {
                    "error": f"The view or table {entity_name} does not exist in the database. Refer to the previously provided list of entities. Allow values are: {', '.join(self.entities.keys())}."
                }
            )

        return json.dumps({entity_name: self.entities[entity_name.lower()]})

    @kernel_function(
        description="Runs an SQL query against the SQL Database to extract information. This function must always be used during the answer generation process. Do not just return the SQL query as the answer.",
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
