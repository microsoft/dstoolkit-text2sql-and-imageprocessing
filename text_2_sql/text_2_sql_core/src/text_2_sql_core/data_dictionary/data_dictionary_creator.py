# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from abc import ABC, abstractmethod
import os
import asyncio
import json
from dotenv import find_dotenv, load_dotenv
import logging
from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional
import random
import re
import networkx as nx
from tenacity import retry, stop_after_attempt, wait_exponential
from text_2_sql_core.connectors.open_ai import OpenAIConnector

logging.basicConfig(level=logging.INFO)


class ForeignKeyRelationship(BaseModel):
    column: str = Field(..., alias="Column")
    foreign_column: str = Field(..., alias="ForeignColumn")

    model_config = ConfigDict(populate_by_name=True)


class EntityRelationship(BaseModel):
    entity: str = Field(..., alias="Entity", exclude=True)
    entity_schema: str = Field(..., alias="Schema", exclude=True)
    foreign_entity: str = Field(..., alias="ForeignEntity")
    foreign_entity_schema: str = Field(..., alias="ForeignSchema")
    foreign_keys: list[ForeignKeyRelationship] = Field(..., alias="ForeignKeys")

    warehouse: Optional[str] = Field(default=None, alias="Warehouse", exclude=True)
    database: Optional[str] = Field(default=None, alias="Database", exclude=True)
    catalog: Optional[str] = Field(default=None, alias="Catalog", exclude=True)

    foreign_warehouse: Optional[str] = Field(default=None, alias="ForeignWarehouse")
    foreign_database: Optional[str] = Field(default=None, alias="ForeignDatabase")
    foreign_catalog: Optional[str] = Field(default=None, alias="ForeignCatalog")

    model_config = ConfigDict(populate_by_name=True)

    def pivot(self):
        """A method to pivot the entity relationship."""
        return EntityRelationship(
            entity=self.foreign_entity,
            entity_schema=self.foreign_entity_schema,
            foreign_entity=self.entity,
            foreign_entity_schema=self.entity_schema,
            foreign_keys=[
                ForeignKeyRelationship(
                    column=foreign_key.foreign_column,
                    foreign_column=foreign_key.column,
                )
                for foreign_key in self.foreign_keys
            ],
            foreign_warehouse=self.warehouse,
            foreign_database=self.database,
            foreign_catalog=self.catalog,
            warehouse=self.foreign_warehouse,
            database=self.foreign_database,
            catalog=self.foreign_catalog,
        )

    def add_foreign_key(self, foreign_key: ForeignKeyRelationship):
        """A method to add a foreign key to the entity relationship."""

        for existing_foreign_key in self.foreign_keys:
            if (
                existing_foreign_key.column == foreign_key.column
                and existing_foreign_key.foreign_column == foreign_key.foreign_column
            ):
                return

        self.foreign_keys.append(foreign_key)

    @computed_field(alias="FQN")
    @property
    def fqn(self) -> str:
        identifiers = [
            self.warehouse,
            self.catalog,
            self.database,
            self.entity_schema,
            self.entity,
        ]
        non_null_identifiers = [x for x in identifiers if x is not None]

        return ".".join(non_null_identifiers)

    @computed_field(alias="ForeignFQN")
    @property
    def foreign_fqn(self) -> str:
        identifiers = [
            self.foreign_warehouse,
            self.foreign_catalog,
            self.foreign_database,
            self.foreign_entity_schema,
            self.foreign_entity,
        ]
        non_null_identifiers = [x for x in identifiers if x is not None]

        return ".".join(non_null_identifiers)

    @classmethod
    def from_sql_row(cls, row, columns):
        """A method to create an EntityRelationship from a SQL row."""
        result = dict(zip(columns, row))

        return cls(
            entity=result["Entity"],
            entity_schema=result["EntitySchema"],
            foreign_entity=result["ForeignEntity"],
            foreign_entity_schema=result["ForeignEntitySchema"],
            foreign_keys=[
                ForeignKeyRelationship(
                    column=result["Column"],
                    foreign_column=result["ForeignColumn"],
                )
            ],
        )


class ColumnItem(BaseModel):
    """A class to represent a column item."""

    name: str = Field(..., alias="Name")
    data_type: str = Field(..., alias="DataType")
    definition: Optional[str] = Field(..., alias="Definition")
    distinct_values: Optional[list] = Field(None, alias="DistinctValues", exclude=True)
    sample_values: Optional[list] = Field(None, alias="SampleValues")

    model_config = ConfigDict(populate_by_name=True)

    def value_store_entry(
        self, entity, distinct_value, excluded_fields_for_database_engine
    ):
        initial_entry = entity.value_store_entry(excluded_fields_for_database_engine)

        initial_entry["FQN"] = f"{entity.fqn}.{self.name}"

        initial_entry["Column"] = self.name
        initial_entry["Value"] = distinct_value
        initial_entry["Synonyms"] = []
        return initial_entry

    @classmethod
    def from_sql_row(cls, row, columns):
        """A method to create a ColumnItem from a SQL row."""
        result = dict(zip(columns, row))
        return cls(
            name=result["Name"],
            data_type=result["DataType"],
            definition=result["Definition"],
        )


class EntityItem(BaseModel):
    """A class to represent an entity item."""

    entity: str = Field(..., alias="Entity")
    definition: Optional[str] = Field(..., alias="Definition")
    name: str = Field(..., alias="Name", exclude=True)
    entity_schema: str = Field(..., alias="Schema")
    entity_name: Optional[str] = Field(default=None, alias="EntityName")
    database: Optional[str] = Field(default=None, alias="Database")
    warehouse: Optional[str] = Field(default=None, alias="Warehouse")
    catalog: Optional[str] = Field(default=None, alias="Catalog")

    entity_relationships: Optional[list[EntityRelationship]] = Field(
        alias="EntityRelationships", default_factory=list
    )

    complete_entity_relationships_graph: Optional[list[str]] = Field(
        alias="CompleteEntityRelationshipsGraph", default_factory=list
    )

    columns: Optional[list[ColumnItem]] = Field(
        ..., alias="Columns", default_factory=list
    )

    model_config = ConfigDict(populate_by_name=True)

    @computed_field(alias="FQN")
    @property
    def fqn(self) -> str:
        identifiers = [
            self.warehouse,
            self.catalog,
            self.database,
            self.entity_schema,
            self.entity,
        ]
        non_null_identifiers = [x for x in identifiers if x is not None]

        return ".".join(non_null_identifiers)

    def value_store_entry(self, excluded_fields_for_database_engine):
        excluded_fields = excluded_fields_for_database_engine + [
            "definition",
            "name",
            "entity_name",
            "entity_relationships",
            "complete_entity_relationships_graph",
            "columns",
        ]
        return self.model_dump(
            by_alias=True, exclude_none=True, exclude=excluded_fields
        )

    @classmethod
    def from_sql_row(cls, row, columns):
        """A method to create an EntityItem from a SQL row."""

        result = dict(zip(columns, row))

        return cls(
            entity=result["Entity"],
            name=result["Entity"],
            entity_schema=result["EntitySchema"],
            definition=result["Definition"],
        )


class DataDictionaryCreator(ABC):
    """An abstract class to extract data dictionary information from a database."""

    def __init__(
        self,
        entities: list[str] = None,
        excluded_entities: list[str] = None,
        excluded_schemas: list[str] = None,
        single_file: bool = False,
        generate_definitions: bool = False,
        output_directory: str = None,
    ):
        """A method to initialize the DataDictionaryCreator class.

        Args:
            entities (list[str], optional): A list of entities to extract. Defaults to None. If None, all entities are extracted.
            excluded_entities (list[str], optional): A list of entities to exclude. Defaults to None.
            excluded_schemas (list[str], optional): A list of schemas to exclude. Defaults to None.
            single_file (bool, optional): A flag to indicate if the data dictionary should be saved to a single file. Defaults to False.
            generate_definitions (bool, optional): A flag to indicate if definitions should be generated. Defaults to True.
        """

        if entities is not None and excluded_entities is not None:
            raise ValueError(
                "Cannot pass both entities and excluded_entities. Please pass only one."
            )

        if excluded_entities is None:
            excluded_entities = []

        self.entities = entities
        self.excluded_entities = [x.lower() for x in excluded_entities]
        self.excluded_schemas = [x.lower() for x in excluded_schemas]
        self.single_file = single_file
        self.generate_definitions = generate_definitions

        self.entity_relationships = {}
        self.relationship_graph = nx.DiGraph()

        self.warehouse = None
        self.database = None
        self.catalog = None

        self.database_engine = None
        self.sql_connector = None

        self.database_semaphore = asyncio.Semaphore(20)
        self.llm_semaphone = asyncio.Semaphore(10)

        if output_directory is None:
            self.output_directory = "."

        self.open_ai_connector = OpenAIConnector()

        load_dotenv(find_dotenv())

    @property
    @abstractmethod
    def extract_table_entities_sql_query(self) -> str:
        """An abstract property to extract table entities from a database.

        Must return 3 columns: Entity, EntitySchema, Definition."""

    @property
    @abstractmethod
    def extract_view_entities_sql_query(self) -> str:
        """An abstract property to extract view entities from a database.

        Must return 3 columns: Entity, EntitySchema, Definition."""

    @abstractmethod
    def extract_columns_sql_query(self, entity: EntityItem) -> str:
        """An abstract method to extract column information from a database.

        Must return 3 columns: Name, DataType, Definition."""

    @property
    @abstractmethod
    def extract_entity_relationships_sql_query(self) -> str:
        """An abstract method to extract entity relationships from a database.

        Must return 6 columns: EntitySchema, Entity, ForeignEntitySchema, ForeignEntity, Column, ForeignColumn.
        """

    def extract_distinct_values_sql_query(
        self, entity: EntityItem, column: ColumnItem
    ) -> str:
        """A method to extract distinct values from a column in a database. Can be sub-classed if needed.

        Args:
            entity (EntityItem): The entity to extract distinct values from.
            column (ColumnItem): The column to extract distinct values from.

        Returns:
            str: The SQL query to extract distinct values from a column.
        """
        return f"""SELECT DISTINCT {column.name} FROM {entity.entity_schema}.{entity.entity} WHERE {column.name} IS NOT NULL ORDER BY {column.name} DESC;"""

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def query_entities(
        self, sql_query: str, cast_to: any = None
    ) -> list[EntityItem]:
        """A method to query a database for entities. Can be sub-classed if needed.

        Args:
            sql_query (str): The SQL query to run.
            cast_to (any, optional): The class to cast the results to. Defaults to None.

        Returns:
            list[EntityItem]: The list of entities.
        """

        return await self.sql_connector.query_execution(sql_query, cast_to=cast_to)

    async def extract_entity_relationships(self) -> list[EntityRelationship]:
        """A method to extract entity relationships from a database.

        Returns:
            list[EntityRelationships]: The list of entity relationships."""

        relationships = await self.query_entities(
            self.extract_entity_relationships_sql_query, cast_to=EntityRelationship
        )

        logging.info(f"Extracted {len(relationships)} relationships")

        for relationship in relationships:
            relationship.warehouse = self.warehouse
            relationship.database = self.database
            relationship.catalog = self.catalog

            relationship.foreign_warehouse = self.warehouse
            relationship.foreign_database = self.database
            relationship.foreign_catalog = self.catalog

        # Duplicate relationships to create a complete graph

        for relationship in relationships:
            if relationship.fqn not in self.entity_relationships:
                self.entity_relationships[relationship.fqn] = {
                    relationship.foreign_fqn: relationship
                }
            else:
                if (
                    relationship.foreign_fqn
                    not in self.entity_relationships[relationship.fqn]
                ):
                    self.entity_relationships[relationship.fqn][
                        relationship.foreign_fqn
                    ] = relationship

                self.entity_relationships[relationship.fqn][
                    relationship.foreign_fqn
                ].add_foreign_key(relationship.foreign_keys[0])

            if relationship.foreign_fqn not in self.entity_relationships:
                self.entity_relationships[relationship.foreign_fqn] = {
                    relationship.fqn: relationship.pivot()
                }
            else:
                if (
                    relationship.fqn
                    not in self.entity_relationships[relationship.foreign_fqn]
                ):
                    self.entity_relationships[relationship.foreign_fqn][
                        relationship.fqn
                    ] = relationship.pivot()

                self.entity_relationships[relationship.foreign_fqn][
                    relationship.fqn
                ].add_foreign_key(relationship.pivot().foreign_keys[0])

    async def build_entity_relationship_graph(self) -> nx.DiGraph:
        """A method to build a complete entity relationship graph."""

        for fqn, foreign_entities in self.entity_relationships.items():
            for foreign_fqn, _ in foreign_entities.items():
                self.relationship_graph.add_edge(fqn, foreign_fqn)

    def get_entity_relationships_from_graph(
        self, entity: str, path=None, result=None, visited=None
    ) -> nx.DiGraph:
        if entity not in self.relationship_graph:
            return []

        if path is None:
            path = [entity]
        if result is None:
            result = []
        if visited is None:
            visited = set()

        # Mark the current node as visited
        visited.add(entity)

        successors = list(self.relationship_graph.successors(entity))
        successors_not_visited = [
            successor for successor in successors if successor not in visited
        ]

        if len(path) == 1 and entity in successors:
            # We can do a self join on the entity in this case but we don't want to propagate this
            result.append(f"{entity} -> {entity}")

        if len(successors_not_visited) == 0 and len(path) > 1:
            # Add the complete path to the result as a string
            result.append(" -> ".join(path))
        else:
            # For each successor (neighbor in the directed path)
            for successor in successors_not_visited:
                new_path = path + [successor]
                # Add the path as a string
                self.get_entity_relationships_from_graph(
                    successor, new_path, result, visited.copy()
                )

        return result

    async def extract_entities_with_definitions(self) -> list[EntityItem]:
        """A method to extract entities with definitions from a database.

        Returns:
            list[EntityItem]: The list of entities."""
        table_entities = await self.query_entities(
            self.extract_table_entities_sql_query, cast_to=EntityItem
        )
        view_entities = await self.query_entities(
            self.extract_view_entities_sql_query, cast_to=EntityItem
        )

        all_entities = table_entities + view_entities

        # Filter entities if entities is not None
        if self.entities is not None:
            all_entities = [
                entity for entity in all_entities if entity.entity in self.entities
            ]

        # Filter entities if excluded_entities is not None
        if len(self.excluded_entities) > 0 or len(self.excluded_schemas):
            all_entities = [
                entity
                for entity in all_entities
                if entity.name.lower() not in self.excluded_entities
                and entity.entity_schema.lower() not in self.excluded_schemas
            ]

        # Add warehouse and database to entities
        for entity in all_entities:
            entity.warehouse = self.warehouse
            entity.database = self.database
            entity.catalog = self.catalog

        return all_entities

    async def write_columns_to_file(self, entity: EntityItem, column: ColumnItem):
        logging.info(f"Saving column values for {column.name}")

        key = f"{entity.fqn}.{column.name}"
        # Ensure the intermediate directories exist
        os.makedirs(f"{self.output_directory}/column_value_store", exist_ok=True)
        with open(
            f"{self.output_directory}/column_value_store/{key}.jsonl",
            "w",
            encoding="utf-8",
        ) as f:
            if column.distinct_values is not None:
                for distinct_value in column.distinct_values:
                    json_string = json.dumps(
                        column.value_store_entry(
                            entity,
                            distinct_value,
                            list(self.excluded_fields_for_database_engine.keys()),
                        ),
                        default=str,
                    )
                    f.write(json_string + "\n")

    async def extract_column_distinct_values(
        self, entity: EntityItem, column: ColumnItem
    ):
        """A method to extract distinct values from a column in a database.

        Args:
            entity (EntityItem): The entity to extract distinct values from.
            column (ColumnItem): The column to extract distinct values from.
        """

        try:
            distinct_values = await self.query_entities(
                self.extract_distinct_values_sql_query(entity, column)
            )

            column.distinct_values = []
            for value in distinct_values:
                if value[column.name] is not None:
                    # Remove any whitespace characters
                    if isinstance(value[column.name], str):
                        column.distinct_values.append(
                            re.sub(r"[\t\n\r\f\v]+", "", value[column.name])
                        )
                    else:
                        column.distinct_values.append(value[column.name])
        except Exception as e:
            logging.error(f"Error extracting values for {column.name}")
            logging.error(e)

        # Handle large set of distinct values
        if column.distinct_values is not None and len(column.distinct_values) > 5:
            column.sample_values = random.sample(column.distinct_values, 5)
        elif column.distinct_values is not None:
            column.sample_values = column.distinct_values

        for data_type in ["string", "nchar", "text", "varchar"]:
            if data_type in column.data_type.lower():
                logging.info(
                    f"""Column {
                        column.name} data type is string based. Writing file."""
                )
                await self.write_columns_to_file(entity, column)
                break

    async def generate_column_definition(self, entity: EntityItem, column: ColumnItem):
        """A method to generate a definition for a column in a database.

        Args:
            entity (EntityItem): The entity the column belongs to.
            column (ColumnItem): The column to generate a definition for."""

        column_definition_system_prompt = """You are an expert in SQL Entity analysis. You must generate a brief definition for this SQL Column. This definition will be used to generate a SQL query with the correct values. Make sure to include a definition of the data contained in this column.

        The definition should be a brief summary of the column as a whole. The definition should be 3-5 sentences long. Apply NO formatting to the definition. The definition should be in plain text without line breaks or special characters.

        You will use this definition later to generate a SQL query. Make sure it will be useful for this purpose in determining the values that should be used in the query and any filtering that should be applied."""

        if column.sample_values is not None and len(column.sample_values) > 0:
            column_definition_system_prompt += """Do not list all sample values in the definition or provide a list of samples. The sample values will be listed separately. The definition should be a brief summary of the column as a whole and any insights drawn from the sample values.

            If there is a pattern in the sample values of the column, such as a common format or that the values are common abbreviations, mention it in the definition. The definition might include: The column contains a list of currency codes in the ISO 4217 format. 'USD' for US Dollar, 'EUR' for Euro, 'GBP' for Pound Sterling.

            If you think the sample values belong to a specific standard, you can mention it in the definition. e.g. The column contains a list of country codes in the ISO 3166-1 alpha-2 format. 'US' for United States, 'GB' for United Kingdom, 'FR' for France. Including the specific standard format code can help the user understand the data better.

            If you think the sample values are not representative of the column as a whole, you can provide a more general definition of the column without mentioning the sample values."""
            stringifed_sample_values = [str(value) for value in column.sample_values]

            column_definition_input = f"""Describe the {column.name} column in the {entity.entity} entity. The following sample values are provided from {
                column.name}: {', '.join(stringifed_sample_values)}."""
        else:
            column_definition_input = f"""Describe the {
                column.name} column in the {entity.entity} entity."""

        if column.definition is not None:
            existing_definition_string = f"""Use this existing definition to aid your understanding: {
                column.definition}"""

            column_definition_input += existing_definition_string

        async with self.llm_semaphone:
            logging.info(f"Generating definition for {column.name}")
            definition = await self.send_request_to_llm(
                column_definition_system_prompt, column_definition_input
            )
            logging.info(f"Definition for {column.name}: {definition}")

        column.definition = definition

    async def extract_columns_with_definitions(
        self, entity: EntityItem
    ) -> list[ColumnItem]:
        """A method to extract column information from a database.

        Args:
            entity (EntityItem): The entity to extract columns from.

        Returns:
            list[ColumnItem]: The list of columns."""

        columns = await self.query_entities(
            self.extract_columns_sql_query(entity), cast_to=ColumnItem
        )

        distinct_value_tasks = []
        definition_tasks = []
        for column in columns:
            distinct_value_tasks.append(
                self.extract_column_distinct_values(entity, column)
            )

            if self.generate_definitions:
                definition_tasks.append(self.generate_column_definition(entity, column))

        await asyncio.gather(*distinct_value_tasks)

        if self.generate_definitions:
            await asyncio.gather(*definition_tasks)

        return columns

    async def send_request_to_llm(self, system_prompt: str, input: str):
        """A method to use GPT to generate a definition for an entity.

        Args:
            system_prompt (str): The system prompt to use.
            input (str): The input to use.

        Returns:
            str: The generated definition."""

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": input,
                    },
                ],
            },
        ]

        return await self.open_ai_connector.run_completion_request(messages)

    async def generate_entity_definition(self, entity: EntityItem):
        """A method to generate a definition for an entity.

        Args:
            entity (EntityItem): The entity to generate a definition for."""
        name_system_prompt = """You are an expert in SQL Entity analysis. You must generate a human readable name for this SQL Entity. This name will be used to select the most appropriate SQL entity to answer a given question. E.g. 'Sales Data', 'Customer Information', 'Product Catalog'."""

        name_input = f"""Provide a human readable name for the {
            entity.entity} entity."""

        definition_system_prompt = """You are an expert in SQL Entity analysis. You must generate a brief definition for this SQL Entity. This definition will be used to select the most appropriate SQL entity to answer a given question. Make sure to include key details of what data is contained in this entity.

        Add information on what sort of questions can be answered using this entity.

        DO NOT list the columns in the definition. The columns will be listed separately. The definition should be a brief summary of the entity as a whole.

        The definition should be 3-5 sentences long. Apply NO formatting to the definition. The definition should be in plain text without line breaks or special characters."""

        definition_input = f"""Describe the {entity.entity} entity. The {
            entity.entity} entity contains the following columns: {', '.join([column.name for column in entity.columns])}."""

        if entity.definition is not None:
            existing_definition_string = f"""Use this existing definition to aid your understanding: {
                entity.definition}"""

            name_input += existing_definition_string
            definition_input += existing_definition_string

        name = await self.send_request_to_llm(name_system_prompt, name_input)
        logging.info(f"Name for {entity.entity}: {name}")
        entity.entity_name = name

        definition = await self.send_request_to_llm(
            definition_system_prompt, definition_input
        )
        logging.info(f"definition for {entity.entity}: {definition}")
        entity.definition = definition

    async def write_entity_to_file(self, entity: EntityItem):
        """A method to write an entity to a file.

        Args:
            entity (EntityItem): The entity to write to file.
        """
        logging.info(f"Saving data dictionary for {entity.entity}")

        # Ensure the intermediate directories exist
        os.makedirs(f"{self.output_directory}/schema_store", exist_ok=True)
        with open(
            f"{self.output_directory}/schema_store/{entity.fqn}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                self.apply_exclusions_to_entity(entity),
                f,
                indent=4,
                default=str,
            )

    async def build_entity_entry(self, entity: EntityItem) -> EntityItem:
        """A method to build an entity entry.

        Args:
            entity (EntityItem): The entity to build an entry for.

        Returns:
            EntityItem: The entity entry."""

        logging.info(f"Building entity entry for {entity.entity}")

        columns = await self.extract_columns_with_definitions(entity)
        entity.columns = columns
        if self.generate_definitions:
            await self.generate_entity_definition(entity)

        # add in relationships
        if entity.fqn in self.entity_relationships:
            entity.entity_relationships = list(
                self.entity_relationships[entity.fqn].values()
            )

        # add in the graph traversal
        entity.complete_entity_relationships_graph = (
            self.get_entity_relationships_from_graph(entity.fqn)
        )

        if self.single_file is False:
            await self.write_entity_to_file(entity)

        return entity

    @property
    def excluded_fields_for_database_engine(self):
        """A method to get the excluded fields for the database engine."""

        # Determine top-level fields to exclude
        filtered_entitiy_specific_fields = {
            field.lower(): ...
            for field in self.sql_connector.excluded_engine_specific_fields
        }

        if filtered_entitiy_specific_fields:
            filtered_entitiy_specific_fields["entity_relationships"] = [
                {
                    field.capitalize(): ...
                    for field in filtered_entitiy_specific_fields.keys()
                }
                | {
                    f"Foreign{field.capitalize()}": ...
                    for field in filtered_entitiy_specific_fields
                }
            ]

        return filtered_entitiy_specific_fields

    def apply_exclusions_to_entity(self, entity: EntityItem) -> dict:
        """A method to apply exclusions to an entity.

        Args:
            entity (EntityItem): The entity to apply exclusions to.

        Returns:
            dict: The dumped entity with exclusions applied."""
        # First, exclude top-level fields
        dumped_data = entity.model_dump(
            by_alias=True, exclude=self.excluded_fields_for_database_engine
        )

        # Now manually handle exclusions for the nested list
        if "EntityRelationships" in dumped_data:
            # Apply exclusions recursively to each item in EntityRelationships list
            for item in dumped_data["EntityRelationships"]:
                for exclusion in self.excluded_fields_for_database_engine.get(
                    "entity_relationships", [{}]
                ):
                    for field, _ in exclusion.items():
                        item.pop(field, None)  # Exclude the field if present

        return dumped_data

    async def create_data_dictionary(self):
        """A method to build a data dictionary from a database. Writes to file."""
        entities = await self.extract_entities_with_definitions()

        await self.extract_entity_relationships()

        await self.build_entity_relationship_graph()

        entity_tasks = []
        for entity in entities:
            entity_tasks.append(self.build_entity_entry(entity))

        data_dictionary = await asyncio.gather(*entity_tasks)

        # Save data dictionary to file
        if self.single_file:
            logging.info("Saving data dictionary to entities.json")
            # Ensure the intermediate directories exist
            os.makedirs(f"{self.output_directory}/schema_store", exist_ok=True)
            with open(
                f"{self.output_directory}/schema_store/entities.json",
                "w",
                encoding="utf-8",
            ) as f:
                data_dictionary_dump = [
                    self.apply_exclusions_to_entity(entity)
                    for entity in data_dictionary
                ]
                json.dump(
                    data_dictionary_dump,
                    f,
                    indent=4,
                    default=str,
                )
