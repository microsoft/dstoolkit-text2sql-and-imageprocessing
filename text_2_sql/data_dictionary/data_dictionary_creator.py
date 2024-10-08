# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from abc import ABC, abstractmethod
import aioodbc
import os
import asyncio
import json
from dotenv import find_dotenv, load_dotenv
import logging
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

logging.basicConfig(level=logging.INFO)


class ColumnItem(BaseModel):
    """A class to represent a column item."""

    name: str = Field(..., alias="Name")
    type: str = Field(..., alias="Type")
    definition: Optional[str] = Field(..., alias="Definition")
    distinct_values: Optional[list[str]] = Field(
        None, alias="DistinctValues", exclude=True
    )
    allowed_values: Optional[list[str]] = Field(None, alias="AllowedValues")
    sample_values: Optional[list[str]] = Field(None, alias="SampleValues")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_sql_row(cls, row, columns):
        """A method to create a ColumnItem from a SQL row."""
        result = dict(zip(columns, row))
        return cls(
            name=result["Name"], type=result["Type"], definition=result["Definition"]
        )


class EntityItem(BaseModel):
    """A class to represent an entity item."""

    entity: str = Field(..., alias="Entity")
    description: Optional[str] = Field(..., alias="Description")
    name: str = Field(..., alias="Name", exclude=True)
    schema: str = Field(..., alias="Schema", exclude=True)

    columns: Optional[list[ColumnItem]] = Field(
        ..., alias="Columns", default_factory=list
    )

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_sql_row(cls, row, columns):
        """A method to create an EntityItem from a SQL row."""

        result = dict(zip(columns, row))

        entity = f"{result['EntitySchema']}.{result['Entity']}"
        return cls(
            entity=entity,
            name=result["Entity"],
            schema=result["EntitySchema"],
            description=result["Description"],
        )


class DataDictionaryCreator(ABC):
    """An abstract class to extract data dictionary information from a database."""

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

        self.entities = entities
        self.excluded_entities = excluded_entities
        self.single_file = single_file

        load_dotenv(find_dotenv())

    @property
    @abstractmethod
    def extract_table_entities_sql_query(self) -> str:
        """An abstract property to extract table entities from a database.

        Must return 3 columns: Entity, EntitySchema, Description."""

    @property
    @abstractmethod
    def extract_view_entities_sql_query(self) -> str:
        """An abstract property to extract view entities from a database.

        Must return 3 columns: Entity, EntitySchema, Description."""

    @abstractmethod
    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """An abstract method to extract column information from a database.

        Must return 3 columns: Name, Type, Definition."""

    def extract_distinct_values_sql_query(
        self, entity: EntityItem, column: ColumnItem
    ) -> str:
        """A method to extract distinct values from a column in a database."""
        return f"""SELECT DISTINCT {column.name} FROM {entity.entity} ORDER BY {column.name} DESC;"""

    async def query_entities(
        self, sql_query: str, cast_to: any = None
    ) -> list[EntityItem]:
        """A method to query a database for entities. Can be sub-classed if needed."""
        connection_string = os.environ["Text2Sql__DatabaseConnectionString"]

        logging.info(f"Running query: {sql_query}")
        results = []
        async with await aioodbc.connect(dsn=connection_string) as sql_db_client:
            async with sql_db_client.cursor() as cursor:
                await cursor.execute(sql_query)

                columns = [column[0] for column in cursor.description]

                rows = await cursor.fetchall()

                for row in rows:
                    if cast_to:
                        results.append(cast_to.from_sql_row(row, columns))
                    else:
                        results.append(dict(zip(columns, row)))

        return results

    async def extract_entities_with_descriptions(self):
        """A method to extract entities with descriptions from a database."""
        table_entities = await self.query_entities(
            self.extract_table_entities_sql_query, cast_to=EntityItem
        )
        view_entities = await self.query_entities(
            self.extract_view_entities_sql_query, cast_to=EntityItem
        )

        all_entities = table_entities + view_entities

        # Filter entities if entities is not None
        if self.entities:
            all_entities = [
                entity for entity in all_entities if entity.entity in self.entities
            ]

        # Filter entities if excluded_entities is not None
        if self.excluded_entities:
            all_entities = [
                entity
                for entity in all_entities
                if entity.entity not in self.excluded_entities
            ]

        return all_entities

    async def extract_column_distinct_values(
        self, entity: EntityItem, column: ColumnItem
    ):
        """A method to extract distinct values from a column in a database."""

        try:
            distinct_values = await self.query_entities(
                self.extract_distinct_values_sql_query(entity, column)
            )

            column.distinct_values = [value[column.name] for value in distinct_values]
        except Exception as e:
            logging.error(f"Error extracting distinct values for {column.name}")
            logging.error(e)

    async def extract_columns_with_definitions(
        self, entity: EntityItem
    ) -> list[ColumnItem]:
        """A method to extract column information from a database."""

        columns = await self.query_entities(
            self.extract_columns_sql_query(entity), cast_to=ColumnItem
        )

        distinct_value_tasks = []
        for column in columns:
            distinct_value_tasks.append(
                self.extract_column_distinct_values(entity, column)
            )

        await asyncio.gather(*distinct_value_tasks)

        return columns

    async def build_entity_entry(self, entity: EntityItem):
        """A method to build an entity entry."""

        logging.info(f"Building entity entry for {entity.entity}")

        columns = await self.extract_columns_with_definitions(entity)

        entity.columns = columns

        return entity

    async def create_data_dictionary(self):
        """A method to build a data dictionary from a database. Writes to file."""
        entities = await self.extract_entities_with_descriptions()

        entity_tasks = []
        for entity in entities:
            entity_tasks.append(self.build_entity_entry(entity))

        data_dictionary = await asyncio.gather(*entity_tasks)

        # Save data dictionary to file
        if self.single_file:
            logging.info("Saving data dictionary to entities.json")
            with open("entities.json", "w", encoding="utf-8") as f:
                json.dump(data_dictionary.model_dump(by_alias=True), f, indent=4)
        else:
            for entity in data_dictionary:
                logging.info(f"Saving data dictionary for {entity.entity}")
                with open(f"{entity.entity}.json", "w", encoding="utf-8") as f:
                    json.dump(entity.model_dump(by_alias=True), f, indent=4)
