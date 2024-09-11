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
    SearchIndexer,
    FieldMapping,
    SimpleField,
    ComplexField,
    IndexingParameters,
    IndexingParametersConfiguration,
    BlobIndexerDataToExtract,
    IndexerExecutionEnvironment,
    BlobIndexerParsingMode,
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
        self.indexer_type = IndexerType.TEXT_2_SQL
        super().__init__(suffix, rebuild)

        self.parsing_mode = BlobIndexerParsingMode.JSON_LINES

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
                name="Columns",
                collection=True,
                fields=[
                    SearchableField(name="Name", type=SearchFieldDataType.String),
                    SearchableField(name="Definition", type=SearchFieldDataType.String),
                    SearchableField(name="Type", type=SearchFieldDataType.String),
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
            SearchableField(
                name="ColumnNames",
                type=SearchFieldDataType.String,
                collection=True,
                hidden=True,
            ),  # This is needed to enable semantic searching against the column names as complex field types are not used.
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
                ],
                keywords_fields=[
                    SemanticField(field_name="ColumnNames"),
                    SemanticField(field_name="Entity"),
                ],
            ),
        )

        semantic_search = SemanticSearch(configurations=[semantic_config])

        return semantic_search

    def get_skills(self) -> list:
        """Get the skillset for the indexer.

        Returns:
            list: The skillsets  used in the indexer"""

        embedding_skill = self.get_vector_skill(
            "/document", "/document/Description", target_name="DescriptionEmbedding"
        )

        skills = [embedding_skill]

        return skills

    def get_indexer(self) -> SearchIndexer:
        """This function returns the indexer for rag document.

        Returns:
            SearchIndexer: The indexer for rag document"""

        # Only place on schedule if it is not a test deployment
        if self.test:
            schedule = None
            batch_size = 4
        else:
            schedule = {"interval": "PT24H"}
            batch_size = 16

        if self.environment.use_private_endpoint:
            execution_environment = IndexerExecutionEnvironment.PRIVATE
        else:
            execution_environment = IndexerExecutionEnvironment.STANDARD

        indexer_parameters = IndexingParameters(
            batch_size=batch_size,
            configuration=IndexingParametersConfiguration(
                data_to_extract=BlobIndexerDataToExtract.CONTENT_AND_METADATA,
                query_timeout=None,
                execution_environment=execution_environment,
                fail_on_unprocessable_document=False,
                fail_on_unsupported_content_type=False,
                index_storage_metadata_only_for_oversized_documents=True,
                indexed_file_name_extensions=".jsonl",
                parsing_mode=self.parsing_mode,
            ),
            max_failed_items=5,
        )

        indexer = SearchIndexer(
            name=self.indexer_name,
            description="Indexer to sql entities and generate embeddings",
            skillset_name=self.skillset_name,
            target_index_name=self.index_name,
            data_source_name=self.data_source_name,
            schedule=schedule,
            output_field_mappings=[
                FieldMapping(
                    source_field_name="/document/Entity", target_field_name="Entity"
                ),
                FieldMapping(
                    source_field_name="/document/EntityName",
                    target_field_name="EntityName",
                ),
                FieldMapping(
                    source_field_name="/document/Description",
                    target_field_name="Description",
                ),
                FieldMapping(
                    source_field_name="/document/DescriptionEmbedding",
                    target_field_name="DescriptionEmbedding",
                ),
                FieldMapping(
                    source_field_name="/document/Columns",
                    target_field_name="Columns",
                ),
                FieldMapping(
                    source_field_name="/document/Columns/*/Name",
                    target_field_name="ColumnNames",
                ),
            ],
            parameters=indexer_parameters,
        )

        return indexer
