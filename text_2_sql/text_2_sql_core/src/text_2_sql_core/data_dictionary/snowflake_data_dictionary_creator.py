# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from data_dictionary_creator import DataDictionaryCreator, EntityItem
import asyncio
import snowflake.connector
import logging
import os

from text_2_sql_core.utils.database import DatabaseEngine
from tenacity import retry, stop_after_attempt, wait_exponential


class SnowflakeDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, **kwargs):
        """A method to initialize the DataDictionaryCreator class."""

        excluded_schemas = ["INFORMATION_SCHEMA"]
        super().__init__(excluded_schemas=excluded_schemas, **kwargs)

        self.database = os.environ["Text2Sql__DatabaseName"]
        self.warehouse = os.environ["Text2Sql__Snowflake__Warehouse"]
        self.database_engine = DatabaseEngine.SNOWFLAKE

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
        """A property to extract entity relationships from a Snowflake database."""
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

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
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

        async with self.database_semaphore:
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
