from abc import ABC, abstractmethod
import aioodbc
import os
import asyncio


class DataDictionaryCreator(ABC):
    """An abstract class to extract data dictionary information from a database."""

    @property
    @abstractmethod
    def extract_table_entities_sql_query(self) -> str:
        """An abstract property to extract table entities from a database.

        Must return 3 columns: Entity, Schema, Description."""

    @property
    @abstractmethod
    def extract_view_entities_sql_query(self) -> str:
        """An abstract property to extract view entities from a database.

        Must return 3 columns: Entity, Schema, Description."""

    @abstractmethod
    def extract_columns_sql_query(self, entity, schema) -> str:
        """An abstract method to extract column information from a database.

        Must return 3 columns: Name, Type, Definition."""

    def extract_distinct_values_sql_query(self, entity, schema, column) -> str:
        """A method to extract distinct values from a column in a database."""
        return f"""SELECT DISTINCT {column} FROM {schema}.{entity};"""

    async def query_entities(self, sql_query: str):
        """A method to query a database for entities. Can be sub-classed if needed."""
        connection_string = os.environ["Text2Sql__DatabaseConnectionString"]
        async with await aioodbc.connect(dsn=connection_string) as sql_db_client:
            async with sql_db_client.cursor() as cursor:
                await cursor.execute(sql_query)

                columns = [column[0] for column in cursor.description]

                rows = await cursor.fetchall()
                results = [dict(zip(columns, returned_row)) for returned_row in rows]

        return results

    async def extract_entities_with_descriptions(self):
        table_entities = await self.query_entities(
            self.extract_table_entities_sql_query
        )
        view_entities = await self.query_entities(self.extract_view_entities_sql_query)

        all_entities = table_entities + view_entities

        return all_entities

    async def extract_column_distinct_values(self, entity, schema, column):
        distinct_values = await self.query_entities(
            self.extract_distinct_values_sql_query(entity, schema, column)
        )

        return distinct_values

    async def extract_columns_with_definitions(self, entity, schema):
        """A method to extract column information from a database."""
        columns = await self.query_entities(
            self.extract_columns_sql_query(entity, schema)
        )

        distinct_value_tasks = []
        for column in columns:
            distinct_value_tasks.append(
                self.extract_column_distinct_values(entity, schema, column["Name"])
            )

        distinct_values = await asyncio.gather(*distinct_value_tasks)

        for column, distinct_values_for_column in zip(columns, distinct_values):
            column["DistinctValues"] = distinct_values_for_column

        return columns
