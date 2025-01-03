# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    DataDictionaryCreator,
    EntityItem,
)
import os

from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.postgresql_sql import PostgresSqlConnector


class PostgresqlDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, **kwargs):
        """A method to initialize the DataDictionaryCreator class."""
        super().__init__(**kwargs)

        self.database = os.environ["Text2Sql__DatabaseName"]
        self.database_engine = DatabaseEngine.POSTGRESQL

        self.sql_connector = PostgresSqlConnector()

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a PostgreSQL database."""
        return """SELECT
            t.table_name AS entity,
            t.table_schema AS entity_schema,
            pg_catalog.col_description(c.oid, 0) AS definition
        FROM
            information_schema.tables t
        JOIN
            pg_catalog.pg_class c ON c.relname = t.table_name
            AND c.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = t.table_schema)
        WHERE
            t.table_type = 'BASE TABLE'
        ORDER BY entity_schema, entity;"""

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from a PostgreSQL database."""
        return """SELECT
            v.view_name AS entity,
            v.table_schema AS entity_schema,
            pg_catalog.col_description(c.oid, 0) AS definition
        FROM
            information_schema.views v
        JOIN
            pg_catalog.pg_class c ON c.relname = v.view_name
            AND c.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = v.table_schema)
        ORDER BY entity_schema, entity;"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from a PostgreSQL database."""
        return f"""SELECT
            c.column_name AS name,
            c.data_type AS data_type,
            pg_catalog.col_description(t.oid, c.ordinal_position) AS definition
        FROM
            information_schema.columns c
        JOIN
            pg_catalog.pg_class t ON t.relname = c.table_name
            AND t.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = c.table_schema)
        WHERE
            c.table_schema = '{entity.entity_schema}'
            AND c.table_name = '{entity.name}'
        ORDER BY c.ordinal_position;"""

    @property
    def extract_entity_relationships_sql_query(self) -> str:
        """A property to extract entity relationships from a PostgreSQL database."""
        return """SELECT
            tc.table_schema AS entity_schema,
            tc.table_name AS entity,
            rc.unique_constraint_schema AS foreign_entity_schema,
            rc.unique_constraint_name AS foreign_entity_constraint,
            rc.constraint_name AS foreign_key_constraint
        FROM
            information_schema.referential_constraints rc
        JOIN
            information_schema.table_constraints tc
            ON rc.constraint_schema = tc.constraint_schema
            AND rc.constraint_name = tc.constraint_name
        WHERE
            tc.constraint_type = 'FOREIGN KEY'
        ORDER BY
            entity_schema, entity, foreign_entity_schema, foreign_entity_constraint;"""
