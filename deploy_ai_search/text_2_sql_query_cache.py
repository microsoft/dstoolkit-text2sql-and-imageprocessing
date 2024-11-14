# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    SearchField,
    SearchableField,
    SimpleField,
    ComplexField,
)
from ai_search import AISearch
from environment import (
    IndexerType,
)


class Text2SqlQueryCacheAISearch(AISearch):
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
            SimpleField(
                name="Id", type=SearchFieldDataType.String, key=True, retrievable=False
            ),
            SearchableField(
                name="Question",
                type=SearchFieldDataType.String,
                analyzer_name="keyword",
            ),
            SearchField(
                name="QuestionEmbedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=self.environment.open_ai_embedding_dimensions,
                vector_search_profile_name=self.vector_search_profile_name,
            ),
            ComplexField(
                name="SqlQueryDecomposition",
                collection=True,
                fields=[
                    SearchableField(
                        name="SqlQuery",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    ComplexField(
                        name="Schemas",
                        collection=True,
                        fields=[
                            SearchableField(
                                name="Entity",
                                type=SearchFieldDataType.String,
                                filterable=True,
                            ),
                            ComplexField(
                                name="Columns",
                                collection=True,
                                fields=[
                                    SearchableField(
                                        name="Name",
                                        type=SearchFieldDataType.String,
                                    ),
                                    SearchableField(
                                        name="Definition",
                                        type=SearchFieldDataType.String,
                                    ),
                                    SearchableField(
                                        name="DataType", type=SearchFieldDataType.String
                                    ),
                                    SearchableField(
                                        name="AllowedValues",
                                        type=SearchFieldDataType.String,
                                        collection=True,
                                        searchable=False,
                                    ),
                                    SearchableField(
                                        name="SampleValues",
                                        type=SearchFieldDataType.String,
                                        collection=True,
                                        searchable=False,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            SimpleField(
                name="DateLastModified",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
            ),
        ]

        return fields
