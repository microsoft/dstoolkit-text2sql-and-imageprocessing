# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    DataDictionaryCreator,
    EntityItem,
)
import asyncio
import os

from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.snowflake_sql import SnowflakeSqlConnector


class SnowflakeDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, **kwargs):
        """A method to initialize the DataDictionaryCreator class."""

        excluded_schemas = ["INFORMATION_SCHEMA"]
        super().__init__(excluded_schemas=excluded_schemas, **kwargs)

        self.database = os.environ["Text2Sql__Snowflake__Database"]
        self.warehouse = os.environ["Text2Sql__Snowflake__Warehouse"]
        self.database_engine = DatabaseEngine.SNOWFLAKE

        self.sql_connector = SnowflakeSqlConnector()

    """A class to extract data dictionary information from a Snowflake database."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a Snowflake database."""
        return """SELECT
            t.TABLE_NAME AS Entity,
            t.TABLE_SCHEMA AS EntitySchema,
            t.COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.TABLES t
        ORDER BY EntitySchema, Entity"""

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from a Snowflake database."""
        return """SELECT
            v.TABLE_NAME AS Entity,
            v.TABLE_SCHEMA AS EntitySchema,
            v.COMMENT AS Definition
        FROM
            INFORMATION_SCHEMA.VIEWS v
        ORDER BY EntitySchema, Entity"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from a Snowflake database."""
        return f"""SELECT
            COLUMN_NAME AS Name,
            DATA_TYPE AS DataType,
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


if __name__ == "__main__":
    data_dictionary_creator = SnowflakeDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
