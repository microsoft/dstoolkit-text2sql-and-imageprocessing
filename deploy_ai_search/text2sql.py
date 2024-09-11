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
)
from ai_search import AISearch
from environment import (
    IndexerType,
)


class RagDocumentsAISearch(AISearch):
    """This class is used to deploy the sql index."""

    def __init__(self, suffix: str | None = None, rebuild: bool | None = False):
        """Initialize the RagDocumentsAISearch class. This class implements the deployment of the sql index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.SQL
        super().__init__(suffix, rebuild)

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
