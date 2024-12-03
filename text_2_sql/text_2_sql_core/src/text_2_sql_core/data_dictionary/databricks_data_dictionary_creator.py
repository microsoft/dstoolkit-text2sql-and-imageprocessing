# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from data_dictionary_creator import DataDictionaryCreator, EntityItem, DatabaseEngine
import asyncio
from databricks import sql
import logging
import os


class DatabricksDataDictionaryCreator(DataDictionaryCreator):
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

    """A class to extract data dictionary information from Databricks Unity Catalog."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from Databricks Unity Catalog."""
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
        """A property to extract view entities from Databricks Unity Catalog."""
        return f"""SELECT
            v.TABLE_NAME AS Entity,
            v.TABLE_SCHEMA AS EntitySchema,
            NULL AS Definition
        FROM
            INFORMATION_SCHEMA.VIEWS v
        WHERE
            v.TABLE_CATALOG = '{self.catalog}'"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from Databricks Unity Catalog."""
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
        """A property to extract entity relationships from Databricks Unity Catalog."""
        return f"""SELECT
            fk_schema.TABLE_SCHEMA AS EntitySchema,
            fk_tab.TABLE_NAME AS Entity,
            pk_schema.TABLE_SCHEMA AS ForeignEntitySchema,
            pk_tab.TABLE_NAME AS ForeignEntity,
            fk_col.COLUMN_NAME AS [Column],
            pk_col.COLUMN_NAME AS ForeignColumn
        FROM
            INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS fk
        INNER JOIN
            INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS fkc
            ON fk.constraint_name = fkc.constraint_name
        INNER JOIN
            INFORMATION_SCHEMA.TABLES AS fk_tab
            ON fk_tab.TABLE_NAME = fkc.TABLE_NAME AND fk_tab.TABLE_SCHEMA = fkc.TABLE_SCHEMA
        INNER JOIN
            INFORMATION_SCHEMA.SCHEMATA AS fk_schema
            ON fk_tab.TABLE_SCHEMA = fk_schema.TABLE_SCHEMA
        INNER JOIN
            INFORMATION_SCHEMA.TABLES AS pk_tab
            ON pk_tab.TABLE_NAME = fkc.referenced_TABLE_NAME AND pk_tab.TABLE_SCHEMA = fkc.referenced_TABLE_SCHEMA
        INNER JOIN
            INFORMATION_SCHEMA.SCHEMATA AS pk_schema
            ON pk_tab.TABLE_SCHEMA = pk_schema.TABLE_SCHEMA
        INNER JOIN
            INFORMATION_SCHEMA.COLUMNS AS fk_col
            ON fkc.COLUMN_NAME = fk_col.COLUMN_NAME AND fkc.TABLE_NAME = fk_col.TABLE_NAME AND fkc.TABLE_SCHEMA = fk_col.TABLE_SCHEMA
        INNER JOIN
            INFORMATION_SCHEMA.COLUMNS AS pk_col
            ON fkc.referenced_COLUMN_NAME = pk_col.COLUMN_NAME AND fkc.referenced_TABLE_NAME = pk_col.TABLE_NAME AND fkc.referenced_TABLE_SCHEMA = pk_col.TABLE_SCHEMA
        WHERE
            fk.constraint_type = 'FOREIGN KEY'
            AND fk_tab.TABLE_CATALOG = '{self.catalog}'
            AND pk_tab.TABLE_CATALOG = '{self.catalog}'
        ORDER BY
            EntitySchema, Entity, ForeignEntitySchema, ForeignEntity;
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
    data_dictionary_creator = DatabricksDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
