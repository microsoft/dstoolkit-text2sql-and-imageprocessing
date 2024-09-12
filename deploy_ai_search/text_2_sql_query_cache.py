# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    SearchField,
    SearchableField,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticConfiguration,
    SemanticSearch,
    SimpleField,
    ComplexField,
)
from ai_search import AISearch
from environment import (
    IndexerType,
)


class Text2SqlAISearch(AISearch):
    """This class is used to deploy the sql index."""

    def __init__(self, suffix: str | None = None, rebuild: bool | None = False):
        """Initialize the Text2SqlAISearch class. This class implements the deployment of the sql index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.TEXT_2_SQL_QUERY_CACHE
        super().__init__(suffix, rebuild)

    def get_index_fields(self) -> list[SearchableField]:
        """This function returns the index fields for sql index.

        Returns:
            list[SearchableField]: The index fields for sql index"""

        fields = [
            SearchableField(
                name="Question",
                type=SearchFieldDataType.String,
                key=True,
                analyzer_name="keyword",
            ),
            SearchField(
                name="QuestionEmbedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=self.environment.open_ai_embedding_dimensions,
                vector_search_profile_name=self.vector_search_profile_name,
            ),
            SearchableField(
                name="Query", type=SearchFieldDataType.String, filterable=True
            ),
            SearchField(
                name="QueryEmbedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=self.environment.open_ai_embedding_dimensions,
                vector_search_profile_name=self.vector_search_profile_name,
            ),
            SearchableField(
                name="Description",
                type=SearchFieldDataType.String,
                sortable=False,
                filterable=False,
                facetable=False,
            ),
            SearchField(
                name="DescriptionEmbedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=self.environment.open_ai_embedding_dimensions,
                vector_search_profile_name=self.vector_search_profile_name,
            ),
            ComplexField(
                name="Schemas",
                collection=True,
                fields=[
                    SearchableField(
                        name="EntityName",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    ComplexField(
                        name="Columns",
                        collection=True,
                        fields=[
                            SearchableField(
                                name="Name", type=SearchFieldDataType.String
                            ),
                            SearchableField(
                                name="Definition", type=SearchFieldDataType.String
                            ),
                            SearchableField(
                                name="Type", type=SearchFieldDataType.String
                            ),
                            SimpleField(
                                name="AllowedValues",
                                type=SearchFieldDataType.String,
                                collection=True,
                            ),
                            SimpleField(
                                name="SampleValues",
                                type=SearchFieldDataType.String,
                                collection=True,
                            ),
                        ],
                    ),
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
                title_field=SemanticField(field_name="Question"),
                keywords_fields=[
                    SemanticField(field_name="Query"),
                ],
            ),
        )

        semantic_search = SemanticSearch(configurations=[semantic_config])

        return semantic_search
