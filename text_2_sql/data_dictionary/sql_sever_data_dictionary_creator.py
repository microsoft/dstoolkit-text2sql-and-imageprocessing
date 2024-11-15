# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from data_dictionary_creator import DataDictionaryCreator, EntityItem, DatabaseEngine
import asyncio
import os


class SqlServerDataDictionaryCreator(DataDictionaryCreator):
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

        excluded_schemas = ["dbo", "sys"]
        super().__init__(entities, excluded_entities, excluded_schemas, single_file)
        self.database = os.environ["Text2Sql__DatabaseName"]

        self.database_engine = DatabaseEngine.SQL_SERVER

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
            t.TABLE_TYPE = 'BASE TABLE';"""

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
    AND ep.name = 'MS_Description';"""

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
            fk_schema.schema_name AS EntitySchema,
            fk_tab.table_name AS Entity,
            pk_schema.schema_name AS ForeignEntitySchema,
            pk_tab.table_name AS ForeignEntity,
            fk_col.column_name AS [Column],
            pk_col.column_name AS ForeignColumn
        FROM
            INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS fk
        INNER JOIN
            INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS fkc
            ON fk.constraint_name = fkc.constraint_name
        INNER JOIN
            INFORMATION_SCHEMA.TABLES AS fk_tab
            ON fk_tab.table_name = fkc.table_name AND fk_tab.table_schema = fkc.table_schema
        INNER JOIN
            INFORMATION_SCHEMA.SCHEMATA AS fk_schema
            ON fk_tab.table_schema = fk_schema.schema_name
        INNER JOIN
            INFORMATION_SCHEMA.TABLES AS pk_tab
            ON pk_tab.table_name = fkc.referenced_table_name AND pk_tab.table_schema = fkc.referenced_table_schema
        INNER JOIN
            INFORMATION_SCHEMA.SCHEMATA AS pk_schema
            ON pk_tab.table_schema = pk_schema.schema_name
        INNER JOIN
            INFORMATION_SCHEMA.COLUMNS AS fk_col
            ON fkc.column_name = fk_col.column_name AND fkc.table_name = fk_col.table_name AND fkc.table_schema = fk_col.table_schema
        INNER JOIN
            INFORMATION_SCHEMA.COLUMNS AS pk_col
            ON fkc.referenced_column_name = pk_col.column_name AND fkc.referenced_table_name = pk_col.table_name AND fkc.referenced_table_schema = pk_col.table_schema
        WHERE
            fk.constraint_type = 'FOREIGN KEY'
            AND fk_tab.table_catalog = 'your_catalog_name'
            AND pk_tab.table_catalog = 'your_catalog_name'
        ORDER BY
            EntitySchema, Entity, ForeignEntitySchema, ForeignEntity;
        """


if __name__ == "__main__":
    data_dictionary_creator = SqlServerDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
