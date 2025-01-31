# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    DataDictionaryCreator,
    EntityItem,
)
import asyncio
import os

from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.postgres_sql import PostgresSqlConnector


class PostgresDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, **kwargs):
        """A method to initialize the DataDictionaryCreator class."""
        excluded_schemas = ["information_schema", "pg_catalog"]
        super().__init__(excluded_schemas=excluded_schemas, **kwargs)

        self.database = os.environ["Text2Sql__Postgres__Database"]
        self.database_engine = DatabaseEngine.POSTGRES

        self.sql_connector = PostgresSqlConnector()

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a Postgres database."""
        return """SELECT
            t.table_name AS "Entity",
            t.table_schema AS "EntitySchema",
            pg_catalog.obj_description(c.oid, 'pg_class') AS "Definition"
        FROM
            information_schema.tables t
        LEFT JOIN
            pg_catalog.pg_class c
            ON c.relname = t.table_name
            AND c.relnamespace = (
                SELECT oid
                FROM pg_catalog.pg_namespace
                WHERE nspname = t.table_schema
            )
        WHERE
            t.table_type = 'BASE TABLE'
        ORDER BY
            "EntitySchema", "Entity";"""

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from a Postgres database."""
        return """SELECT
            v.table_name AS "Entity",
            v.table_schema AS "EntitySchema",
            pg_catalog.obj_description(c.oid, 'pg_class') AS "Definition"
        FROM
            information_schema.views v
        LEFT JOIN
            pg_catalog.pg_class c
            ON c.relname = v.table_name
            AND c.relnamespace = (
                SELECT oid
                FROM pg_catalog.pg_namespace
                WHERE nspname = v.table_schema
            )
        ORDER BY
            "EntitySchema", "Entity";"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from a Postgres database."""
        return f"""SELECT
            c.attname AS "Name",
            t.typname AS "DataType",
            pgd.description AS "Definition"
        FROM
            pg_attribute c
        INNER JOIN
            pg_class tbl ON c.attrelid = tbl.oid
        INNER JOIN
            pg_namespace ns ON tbl.relnamespace = ns.oid
        INNER JOIN
            pg_type t ON c.atttypid = t.oid
        LEFT JOIN
            pg_description pgd ON pgd.objoid = tbl.oid AND pgd.objsubid = c.attnum
        WHERE
            ns.nspname = '{entity.entity_schema}'
            AND tbl.relname = '{entity.name}'
            AND c.attnum > 0  -- Exclude system columns
        ORDER BY
            c.attnum;"""

    @property
    def extract_entity_relationships_sql_query(self) -> str:
        """A property to extract entity relationships from a Postgres database."""
        return """SELECT
            fk_schema.nspname AS "EntitySchema",
            fk_tab.relname AS "Entity",
            pk_schema.nspname AS "ForeignEntitySchema",
            pk_tab.relname AS "ForeignEntity",
            fk_col.attname AS "Column",
            pk_col.attname AS "ForeignColumn"
        FROM
            pg_constraint fk
        INNER JOIN
            pg_attribute fk_col ON fk.conrelid = fk_col.attrelid AND fk.conkey[1] = fk_col.attnum
        INNER JOIN
            pg_class fk_tab ON fk.conrelid = fk_tab.oid
        INNER JOIN
            pg_namespace fk_schema ON fk_tab.relnamespace = fk_schema.oid
        INNER JOIN
            pg_class pk_tab ON fk.confrelid = pk_tab.oid
        INNER JOIN
            pg_namespace pk_schema ON pk_tab.relnamespace = pk_schema.oid
        INNER JOIN
            pg_attribute pk_col ON fk.confrelid = pk_col.attrelid AND fk.confkey[1] = pk_col.attnum
        ORDER BY
            "EntitySchema", "Entity", "ForeignEntitySchema", "ForeignEntity";"""


if __name__ == "__main__":
    data_dictionary_creator = PostgresDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
