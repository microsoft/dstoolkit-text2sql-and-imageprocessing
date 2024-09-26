from data_dictionary_creator import DataDictionaryCreator


class SqlServerDataDictionaryCreator(DataDictionaryCreator):
    """A class to extract data dictionary information from a SQL Server database."""

    @property
    def extract_table_entities_sql_query(self) -> str:
        """A property to extract table entities from a SQL Server database."""
        return """SELECT
    t.TABLE_NAME AS Entity,
    t.TABLE_SCHEMA AS Schema,
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
    v.TABLE_SCHEMA AS Schema,
    CAST(ep.value AS NVARCHAR(500)) AS Description
FROM
    INFORMATION_SCHEMA.VIEWS v
LEFT JOIN
    sys.extended_properties ep
    ON ep.major_id = OBJECT_ID(v.TABLE_SCHEMA + '.' + v.TABLE_NAME)
    AND ep.minor_id = 0
    AND ep.class = 1
    AND ep.name = 'MS_Description';"""

    def extract_columns_sql_query(self, entity, schema) -> str:
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
    c.TABLE_SCHEMA = '{schema}'
    AND c.TABLE_NAME = '{entity}';"""
