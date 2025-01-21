# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    DataDictionaryCreator,
    EntityItem,
)
import asyncio
import os
from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.tsql_sql import TsqlSqlConnector


class TsqlDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, **kwargs):
        """A method to initialize the DataDictionaryCreator class.

        Args:
            entities (list[str], optional): A list of entities to extract. Defaults to None. If None, all entities are extracted.
            excluded_entities (list[str], optional): A list of entities to exclude. Defaults to None.
            single_file (bool, optional): A flag to indicate if the data dictionary should be saved to a single file. Defaults to False.
        """
        excluded_schemas = ["dbo", "sys"]
        super().__init__(excluded_schemas=excluded_schemas, **kwargs)
        self.database = os.environ["Text2Sql__Tsql__Database"]

        self.database_engine = DatabaseEngine.TSQL

        self.sql_connector = TsqlSqlConnector()

    """A class to extract data dictionary information from a SQL Server database."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a SQL Server database."""
        return """SELECT
            t.TABLE_NAME AS Entity,
            t.TABLE_SCHEMA AS EntitySchema,
            CAST(ep.value AS NVARCHAR(500)) AS Definition
        FROM
            INFORMATION_SCHEMA.TABLES t
        LEFT JOIN
            sys.extended_properties ep
            ON ep.major_id = OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME)
            AND ep.minor_id = 0
            AND ep.class = 1
            AND ep.name = 'MS_Description'
        WHERE
            t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY EntitySchema, Entity;"""

    @property
    def extract_view_entities_sql_query(self) -> str:
        """A property to extract view entities from a SQL Server database."""
        return """SELECT
            v.TABLE_NAME AS Entity,
            v.TABLE_SCHEMA AS EntitySchema,
            CAST(ep.value AS NVARCHAR(500)) AS Definition
        FROM
            INFORMATION_SCHEMA.VIEWS v
        LEFT JOIN
            sys.extended_properties ep
            ON ep.major_id = OBJECT_ID(v.TABLE_SCHEMA + '.' + v.TABLE_NAME)
            AND ep.minor_id = 0
            AND ep.class = 1
        AND ep.name = 'MS_Description'
        ORDER BY EntitySchema, Entity;"""

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """A property to extract column information from a SQL Server database."""
        return f"""SELECT
            c.COLUMN_NAME AS Name,
            c.DATA_TYPE AS DataType,
            CAST(ep.value AS NVARCHAR(500)) AS Definition
        FROM
            INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN
            sys.extended_properties ep
            ON ep.major_id = OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME)
            AND ep.minor_id = c.ORDINAL_POSITION
            AND ep.class = 1
            AND ep.name = 'MS_Description'
        WHERE
            c.TABLE_SCHEMA = '{entity.entity_schema}'
            AND c.TABLE_NAME = '{entity.name}';"""

    @property
    def extract_entity_relationships_sql_query(self) -> str:
        """A property to extract entity relationships from a SQL Server database."""
        return """SELECT
            fk_schema.name AS EntitySchema,
            fk_tab.name AS Entity,
            pk_schema.name AS ForeignEntitySchema,
            pk_tab.name AS ForeignEntity,
            fk_col.name AS [Column],
            pk_col.name AS ForeignColumn
        FROM
            sys.foreign_keys AS fk
        INNER JOIN
            sys.foreign_key_columns AS fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN
            sys.tables AS fk_tab ON fk_tab.object_id = fk.parent_object_id
        INNER JOIN
            sys.schemas AS fk_schema ON fk_tab.schema_id = fk_schema.schema_id
        INNER JOIN
            sys.tables AS pk_tab ON pk_tab.object_id = fk.referenced_object_id
        INNER JOIN
            sys.schemas AS pk_schema ON pk_tab.schema_id = pk_schema.schema_id
        INNER JOIN
            sys.columns AS fk_col ON fkc.parent_object_id = fk_col.object_id AND fkc.parent_column_id = fk_col.column_id
        INNER JOIN
            sys.columns AS pk_col ON fkc.referenced_object_id = pk_col.object_id AND fkc.referenced_column_id = pk_col.column_id
        ORDER BY
            EntitySchema, Entity, ForeignEntitySchema, ForeignEntity;
        """


if __name__ == "__main__":
    data_dictionary_creator = TsqlDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
