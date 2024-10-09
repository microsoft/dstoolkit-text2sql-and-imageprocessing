# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from data_dictionary_creator import DataDictionaryCreator, EntityItem
import asyncio


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

        excluded_entities.extend(
            ["dbo.BuildVersion", "dbo.ErrorLog", "sys.database_firewall_rules"]
        )
        return super().__init__(entities, excluded_entities, single_file)

    """A class to extract data dictionary information from a SQL Server database."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a SQL Server database."""
        return """SELECT
    t.TABLE_NAME AS Entity,
    t.TABLE_SCHEMA AS EntitySchema,
    CAST(ep.value AS NVARCHAR(500)) AS Description
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
    CAST(ep.value AS NVARCHAR(500)) AS Description
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
    c.DATA_TYPE AS Type,
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


if __name__ == "__main__":
    data_dictionary_creator = SqlServerDataDictionaryCreator()
    asyncio.run(data_dictionary_creator.create_data_dictionary())
