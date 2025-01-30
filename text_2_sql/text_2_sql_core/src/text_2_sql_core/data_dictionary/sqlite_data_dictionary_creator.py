# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    DataDictionaryCreator,
    EntityItem,
    ColumnItem,
)
from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.sqlite_sql import SQLiteSqlConnector
import logging
import re

class SQLiteDataDictionaryCreator(DataDictionaryCreator):
    def __init__(self, database_path: str, output_directory: str = None, **kwargs):
        """Initialize the SQLite Data Dictionary Creator.

        Args:
            database_path: Path to the SQLite database file
            output_directory: Directory to write output files to
            **kwargs: Additional arguments passed to DataDictionaryCreator
        """
        super().__init__(**kwargs)
        self.database = database_path
        self.database_engine = DatabaseEngine.SQLITE
        self.output_directory = output_directory if output_directory is not None else "."

        self.sql_connector = SQLiteSqlConnector()
        self.sql_connector.set_database(database_path)

    @property
    def extract_table_entities_sql_query(self) -> str:
        """Extract table entities from SQLite schema."""
        return """
        SELECT
            name as Entity,
            'main' as EntitySchema,
            sql as Definition
        FROM
            sqlite_master
        WHERE
            type='table' AND
            name NOT LIKE 'sqlite_%'
        ORDER BY
            name;
        """

    @property
    def extract_view_entities_sql_query(self) -> str:
        """Extract view entities from SQLite schema."""
        return """
        SELECT
            name as Entity,
            'main' as EntitySchema,
            sql as Definition
        FROM
            sqlite_master
        WHERE
            type='view' AND
            name NOT LIKE 'sqlite_%'
        ORDER BY
            name;
        """

    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """Extract column information for a given entity.

        Args:
            entity: The entity to extract columns for

        Returns:
            SQL query to extract column information
        """
        return f"""
        SELECT
            p.name as Name,
            p.type as DataType,
            p.type || CASE
                WHEN p."notnull" = 1 THEN ' NOT NULL'
                ELSE ''
            END || CASE
                WHEN p.pk = 1 THEN ' PRIMARY KEY'
                ELSE ''
            END as Definition
        FROM
            sqlite_master m
        JOIN
            pragma_table_info(m.name) p
        WHERE
            m.type IN ('table', 'view') AND
            m.name = '{entity.entity}'
        ORDER BY
            p.cid;
        """

    @property
    def extract_entity_relationships_sql_query(self) -> str:
        """Extract foreign key relationships from SQLite schema."""
        return """
        WITH RECURSIVE
        fk_info AS (
            SELECT
                m.name as table_name,
                p."table" as referenced_table,
                p."from" as column_name,
                p."to" as referenced_column
            FROM
                sqlite_master m,
                pragma_foreign_key_list(m.name) p
            WHERE
                m.type = 'table'
        )
        SELECT DISTINCT
            'main' as EntitySchema,
            fk.table_name as Entity,
            'main' as ForeignEntitySchema,
            fk.referenced_table as ForeignEntity,
            fk.column_name as "Column",
            fk.referenced_column as ForeignColumn
        FROM
            fk_info fk
        ORDER BY
            Entity, ForeignEntity;
        """

    def extract_distinct_values_sql_query(self, entity: EntityItem, column: ColumnItem) -> str:
        """Extract distinct values for a column.

        Args:
            entity: The entity containing the column
            column: The column to extract values from

        Returns:
            SQL query to extract distinct values
        """
        # Use single quotes for string literals and double quotes for identifiers
        return f"""
        SELECT DISTINCT "{column.name}"
        FROM "{entity.entity}"
        WHERE "{column.name}" IS NOT NULL
        ORDER BY "{column.name}" DESC
        LIMIT 1000;
        """

    async def extract_column_distinct_values(self, entity: EntityItem, column: ColumnItem):
        """Override to use SQLite-specific query and handling.

        Args:
            entity: The entity to extract distinct values from
            column: The column to extract distinct values from
        """
        try:
            print(f"Executing query for {entity.entity}.{column.name}")
            distinct_values = await self.query_entities(
                self.extract_distinct_values_sql_query(entity, column)
            )
            print(f"Got {len(distinct_values)} distinct values")

            column.distinct_values = []
            for value in distinct_values:
                # value is a tuple with one element since we're selecting a single column
                if value[0] is not None:
                    # Remove any whitespace characters
                    if isinstance(value[0], str):
                        column.distinct_values.append(
                            re.sub(r"[\t\n\r\f\v]+", "", value[0])
                        )
                    else:
                        column.distinct_values.append(value[0])

            # Handle large set of distinct values
            if len(column.distinct_values) > 5:
                column.sample_values = column.distinct_values[:5]  # Take first 5 values
            else:
                column.sample_values = column.distinct_values

            # Write column values to file for string-based columns
            for data_type in ["string", "nchar", "text", "varchar"]:
                if data_type in column.data_type.lower():
                    print(f"Writing {len(column.distinct_values)} values for {entity.entity}.{column.name}")
                    await self.write_columns_to_file(entity, column)
                    break

        except Exception as e:
            logging.error(f"Error extracting values for {entity.entity}.{column.name}")
            logging.error(e)
            raise  # Re-raise to see the actual error

if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 2:
        print("Usage: python sqlite_data_dictionary_creator.py <database_path>")
        sys.exit(1)

    creator = SQLiteDataDictionaryCreator(sys.argv[1])
    asyncio.run(creator.create_data_dictionary())
