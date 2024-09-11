# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    ComplexField,
    SearchableField,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticConfiguration,
    SemanticSearch,
    SimpleField,
)
from ai_search import AISearch
from environment import (
    IndexerType,
)
import logging
import json


class Text2SqlAISearch(AISearch):
    """This class is used to deploy the sql index."""

    def __init__(self, suffix: str | None = None, rebuild: bool | None = False):
        """Initialize the Text2SqlAISearch class. This class implements the deployment of the sql index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.TEXT_2_SQL
        super().__init__(suffix, rebuild)

        self.entities = []

    def get_index_fields(self) -> list[SearchableField]:
        """This function returns the index fields for sql index.

        Returns:
            list[SearchableField]: The index fields for sql index"""

        fields = [
            SearchableField(
                name="Entity",
                type=SearchFieldDataType.String,
                key=True,
                analyzer_name="keyword",
            ),
            SearchableField(
                name="EntityName", type=SearchFieldDataType.String, filterable=True
            ),
            SimpleField(name="SelectFromEntity", type=SearchFieldDataType.String),
            SearchableField(
                name="Description",
                type=SearchFieldDataType.String,
                sortable=False,
                filterable=False,
                facetable=False,
            ),
            SearchableField(
                name="Selector",
                type=SearchFieldDataType.String,
                sortable=False,
                filterable=False,
                facetable=False,
            ),
            SearchableField(
                name="Sections",
                type=SearchFieldDataType.String,
                collection=True,
            ),
            ComplexField(
                name="Columns",
                collection=True,
                fields=[
                    SearchableField(name="Name", type=SearchFieldDataType.String),
                    SearchableField(name="Definition", type=SearchFieldDataType.String),
                    SearchableField(name="Type", type=SearchFieldDataType.String),
                ],
            ),
        ]

        return fields

    def get_semantic_search(self) -> SemanticSearch:
        """This function returns the semantic search configuration for sql index

        Returns:
            SemanticSearch: The semantic search configuration"""

        semantic_config = SemanticConfiguration(
            name=self.semantic_config_name,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="EntityName"),
                content_fields=[
                    SemanticField(field_name="Description"),
                    SemanticField(field_name="Selector"),
                    SemanticField(field_name="Description"),
                ],
                keywords_fields=[
                    SemanticField(field_name="Column/Name"),
                    SemanticField(field_name="Column/Definition"),
                    SemanticField(field_name="Column/Type"),
                ],
            ),
        )

        semantic_search = SemanticSearch(configurations=[semantic_config])

        return semantic_search

    def load_entities(self):
        """Load the views from the JSON file and formats into memory."""
        with open(
            "../text_2_sql/plugins/vector_based_sql_plugin/entities.json",
            "r",
            encoding="utf-8",
        ) as file:
            entities = json.load(file)

            def rename_keys(d: dict, key_mapping: dict) -> dict:
                """Rename the keys in the dictionary.

                Args:
                    d (dict): The dictionary to rename the keys.
                    key_mapping (dict): The mapping of the keys to rename.

                Returns:
                    dict: The dictionary with the renamed keys.
                """
                return {key_mapping.get(k): v for k, v in d.items()}

            top_level_renaming_map = {
                "view_name": "EntityName",
                "table_name": "EntityName",
                "entity": "Entity",
                "columns": "Columns",
                "description": "Description",
                "selector": "Selector",
            }

            # Load tables and views
            for entity in entities["tables"].extend(entities["views"]):
                entity_object = rename_keys(entity.copy(), top_level_renaming_map)

                entity = entity_object["Entity"]
                entity_object["SelectFromEntity"] = f"{self.database}.{entity}"

                entity_object["Columns"] = rename_keys(
                    entity_object["Columns"],
                    {"name": "Name", "definition": "Definition", "type": "Type"},
                )
                self.entities.append(entity_object)

        logging.info("Entities loaded into memory.")

    def deploy_entities(self):
        """Upload the entities to AI search"""

        self.index_client.upload_documents(documents=self.entities)

        logging.info("Entities uploaded to AI search.")

    def deploy(self):
        """Deploy the sql index."""
        super().deploy()
        self.load_entities()
        self.deploy_entities()
