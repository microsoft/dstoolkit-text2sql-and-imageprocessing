# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from data_dictionary_creator import DataDictionaryCreator, EntityItem
import asyncio
import snowflake.connector
import logging
import os


class SnowflakeDataDictionaryCreator(DataDictionaryCreator):
    def __init__(
        self,
        entities: list[str] = None,
        excluded_entities: list[str] = None,
        single_file: bool = False,
    ):
        """A method to initialize the DataDictionaryCreator class.

        Args:
            entities (list[str], optional): A list of entities to extract. Defaults to None. If None, all entities are extracted.
            excluded_entities (list[str], optional): A list of entities to exclude. Defaults to None.
            single_file (bool, optional): A flag to indicate if the data dictionary should be saved to a single file. Defaults to False.
        """
        if excluded_entities is None:
            excluded_entities = []

        excluded_schemas = ["INFORMATION_SCHEMA"]
        return super().__init__(
            entities, excluded_entities, excluded_schemas, single_file
        )

    """A class to extract data dictionary information from a Snowflake database."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a Snowflake database."""
        return """SELECT
            t.TABLE_NAME AS Entity,
            t.TABLE_SCHEMA AS EntitySchema,
            t.COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.TABLES t"""

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from a Snowflake database."""
        return """SELECT
            v.TABLE_NAME AS Entity,
            v.TABLE_SCHEMA AS EntitySchema,
            v.COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.VIEWS v"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from a Snowflake database."""
        return f"""SELECT
            COLUMN_NAME AS Name,
            DATA_TYPE AS Type,
            COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.COLUMNS
        WHERE
            TABLE_SCHEMA = '{entity.entity_schema}'
            AND TABLE_NAME = '{entity.name}';"""

    @property
    def extract_entity_relationships_sql_query(self) -> str:
        """A property to extract entity relationships from a SQL Server database."""
        return """SELECT
            tc.table_schema AS EntitySchema,
            tc.table_name AS Entity,
            rc.unique_constraint_schema AS ForeignEntitySchema,
            rc.unique_constraint_name AS ForeignEntityConstraint,
            rc.constraint_name AS ForeignKeyConstraint
        FROM
            information_schema.referential_constraints rc
        JOIN
            information_schema.table_constraints tc
            ON rc.constraint_schema = tc.constraint_schema
            AND rc.constraint_name = tc.constraint_name
        WHERE
            tc.constraint_type = 'FOREIGN KEY'
        ORDER BY
            EntitySchema, Entity, ForeignEntitySchema, ForeignEntityConstraint;
        """

    async def query_entities(
        self, sql_query: str, cast_to: any = None
    ) -> list[EntityItem]:
        """A method to query a database for entities using Snowflake Connector. Overrides the base class method.

        Args:
            sql_query (str): The SQL query to run.
            cast_to (any, optional): The class to cast the results to. Defaults to None.

        Returns:
            list[EntityItem]: The list of entities.
        """
        logging.info(f"Running query: {sql_query}")
        results = []

        # Create a connection to Snowflake, without specifying a schema
        conn = snowflake.connector.connect(
            user=os.environ["Text2Sql__Snowflake__User"],
            password=os.environ["Text2Sql__Snowflake__Password"],
            account=os.environ["Text2Sql__Snowflake__Account"],
            warehouse=os.environ["Text2Sql__Snowflake__Warehouse"],
            database=os.environ["Text2Sql__DatabaseName"],
        )

        try:
            # Using the connection to create a cursor
            cursor = conn.cursor()

            # Execute the query
            await asyncio.to_thread(cursor.execute, sql_query)

            # Fetch column names
            columns = [col[0] for col in cursor.description]

            # Fetch rows
            rows = await asyncio.to_thread(cursor.fetchall)

            # Process rows
            for row in rows:
                if cast_to:
                    results.append(cast_to.from_sql_row(row, columns))
                else:
                    results.append(dict(zip(columns, row)))

        finally:
            cursor.close()
            conn.close()

        return results


if __name__ == "__main__":
    data_dictionary_creator = SnowflakeDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
