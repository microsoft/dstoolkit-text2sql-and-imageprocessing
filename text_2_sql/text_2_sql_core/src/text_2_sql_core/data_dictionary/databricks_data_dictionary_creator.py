# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    DataDictionaryCreator,
    EntityItem,
    ColumnItem,
)
import asyncio
import os
from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.databricks_sql import DatabricksSqlConnector


class DatabricksDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, **kwargs):
        """A method to initialize the DataDictionaryCreator class."""

        excluded_schemas = ["INFORMATION_SCHEMA"]
        super().__init__(excluded_schemas=excluded_schemas, **kwargs)

        self.catalog = os.environ["Text2Sql__Databricks__Catalog"]
        self.database_engine = DatabaseEngine.DATABRICKS

        self.sql_connector = DatabricksSqlConnector()

    """A class to extract data dictionary information from Databricks Unity Catalog."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from Databricks Unity Catalog."""
        return f"""SELECT
            t.TABLE_NAME AS Entity,
            t.TABLE_SCHEMA AS EntitySchema,
            t.COMMENT AS Definition
        FROM
            {self.catalog}.INFORMATION_SCHEMA.TABLES t
        ORDER BY EntitySchema, Entity
        """

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from Databricks Unity Catalog."""
        return f"""SELECT
            v.TABLE_NAME AS Entity,
            v.TABLE_SCHEMA AS EntitySchema,
            NULL AS Definition
        FROM
            {self.catalog}.INFORMATION_SCHEMA.VIEWS v
        ORDER BY EntitySchema, Entity
        """

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from Databricks Unity Catalog."""
        return f"""SELECT
            COLUMN_NAME AS Name,
            DATA_TYPE AS DataType,
            COMMENT AS Definition
        FROM
            {self.catalog}.INFORMATION_SCHEMA.COLUMNS
        WHERE
            TABLE_SCHEMA = '{entity.entity_schema}'
            AND TABLE_NAME = '{entity.name}';"""

    @property
    def extract_entity_relationships_sql_query(self) -> str:
        """A property to extract entity relationships from Databricks Unity Catalog."""
        return f"""SELECT
            fk_schema.schema_name AS EntitySchema,
            fk_tab.TABLE_NAME AS Entity,
            pk_schema.schema_name AS ForeignEntitySchema,
            pk_tab.TABLE_NAME AS ForeignEntity,
            fk_col.COLUMN_NAME AS Column,
            pk_col.COLUMN_NAME AS ForeignColumn
        FROM
            {self.catalog}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS fk
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS fkc
            ON fk.constraint_name = fkc.constraint_name
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.TABLES AS fk_tab
            ON fk_tab.TABLE_NAME = fkc.TABLE_NAME AND fk_tab.TABLE_SCHEMA = fkc.TABLE_SCHEMA
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.SCHEMATA AS fk_schema
            ON fk_tab.TABLE_SCHEMA = fk_schema.schema_name
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.TABLES AS pk_tab
            ON pk_tab.TABLE_NAME = fkc.table_name AND pk_tab.TABLE_SCHEMA = fkc.table_schema
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.SCHEMATA AS pk_schema
            ON pk_tab.TABLE_SCHEMA = pk_schema.schema_name
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.COLUMNS AS fk_col
            ON fkc.COLUMN_NAME = fk_col.COLUMN_NAME AND fkc.TABLE_NAME = fk_col.TABLE_NAME AND fkc.TABLE_SCHEMA = fk_col.TABLE_SCHEMA
        INNER JOIN
            {self.catalog}.INFORMATION_SCHEMA.COLUMNS AS pk_col
            ON fkc.column_name = pk_col.COLUMN_NAME AND fkc.table_name = pk_col.TABLE_NAME AND fkc.table_schema = pk_col.TABLE_SCHEMA
        WHERE
            fk.constraint_type = 'FOREIGN KEY'
        ORDER BY
            EntitySchema, Entity, ForeignEntitySchema, ForeignEntity;
        """

    def extract_distinct_values_sql_query(
        self, entity: EntityItem, column: ColumnItem
    ) -> str:
        """A method to extract distinct values from a column in a database. Can be sub-classed if needed.

        Args:
            entity (EntityItem): The entity to extract distinct values from.
            column (ColumnItem): The column to extract distinct values from.

        Returns:
            str: The SQL query to extract distinct values from a column.
        """
        return f"""SELECT DISTINCT {column.name} FROM {self.catalog}.{entity.entity_schema}.{entity.entity} WHERE {column.name} IS NOT NULL ORDER BY {column.name} DESC;"""


if __name__ == "__main__":
    data_dictionary_creator = DatabricksDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
