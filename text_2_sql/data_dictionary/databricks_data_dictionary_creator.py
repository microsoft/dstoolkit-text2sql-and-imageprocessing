# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from data_dictionary_creator import DataDictionaryCreator, EntityItem, DatabaseEngine
import asyncio
from databricks import sql
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

        excluded_schemas = []
        super().__init__(entities, excluded_entities, excluded_schemas, single_file)

        self.catalog = os.environ["Text2Sql__Databricks__Catalog"]
        self.database_engine = DatabaseEngine.DATABRICKS

    """A class to extract data dictionary information from a Snowflake database."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a Snowflake database."""
        return f"""SELECT
            t.TABLE_NAME AS Entity,
            t.TABLE_SCHEMA AS EntitySchema,
            t.COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.TABLES t
        WHERE
            t.TABLE_CATALOG = '{self.catalog}'
        """

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from a Snowflake database."""
        return """SELECT
            v.TABLE_NAME AS Entity,
            v.TABLE_SCHEMA AS EntitySchema
            NULL AS Definition
        FROM
            INFORMATION_SCHEMA.VIEWS v
        WHERE
            v.TABLE_CATALOG = '{self.catalog}'"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from a Snowflake database."""
        return f"""SELECT
            COLUMN_NAME AS Name,
            DATA_TYPE AS Type,
            COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.COLUMNS
        WHERE
            TABLE_CATALOG = '{self.catalog}'
            AND TABLE_SCHEMA = '{entity.entity_schema}'
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

    async def query_entities(self, sql_query: str, cast_to: any = None) -> list[dict]:
        """
        A method to query a Databricks SQL endpoint for entities.

        Args:
            sql_query (str): The SQL query to run.
            cast_to (any, optional): The class to cast the results to. Defaults to None.

        Returns:
            list[dict]: The list of entities or processed rows.
        """
        logging.info(f"Running query: {sql_query}")
        results = []

        # Set up connection parameters for Databricks SQL endpoint
        connection = sql.connect(
            server_hostname=os.environ["Text2Sql__Databricks__ServerHostname"],
            http_path=os.environ["Text2Sql__Databricks__HttpPath"],
            access_token=os.environ["Text2Sql__Databricks__AccessToken"],
        )

        try:
            # Create a cursor
            cursor = connection.cursor()

            # Execute the query in a thread-safe manner
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

        except Exception as e:
            logging.error(f"Error while executing query: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

        return results


if __name__ == "__main__":
    data_dictionary_creator = SnowflakeDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
