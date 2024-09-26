from abc import ABC, abstractmethod
import aioodbc
import os


class DataDictionaryCreator(ABC):
    """An abstract class to extract data dictionary information from a database."""

    @property
    @abstractmethod
    def extract_table_entities_sql_query(self) -> str:
        """An abstract property to extract table entities from a database.

        Must return 3 columns: Entity, Schema, Description."""
        pass

    @property
    @abstractmethod
    def extract_view_entities_sql_query(self) -> str:
        """An abstract property to extract view entities from a database.

        Must return 3 columns: Entity, Schema, Description."""
        pass

    async def query_entities(self, sql_query: str):
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
