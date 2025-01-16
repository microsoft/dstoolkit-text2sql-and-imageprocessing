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
    InputFieldMappingEntry,
    SearchIndexer,
    FieldMapping,
    IndexingParameters,
    IndexingParametersConfiguration,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SimpleField,
    ComplexField,
    BlobIndexerDataToExtract,
    IndexerExecutionEnvironment,
)
from ai_search import AISearch
from environment import (
    IndexerType,
)


class RagDocumentsAISearch(AISearch):
    """This class is used to deploy the rag document index."""

    def __init__(
        self,
        suffix: str | None = None,
        rebuild: bool | None = False,
        enable_page_by_chunking=False,
    ):
        """Initialize the RagDocumentsAISearch class. This class implements the deployment of the rag document index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.RAG_DOCUMENTS
        super().__init__(suffix, rebuild)

        if enable_page_by_chunking is not None:
            self.enable_page_by_chunking = enable_page_by_chunking
        else:
            self.enable_page_by_chunking = False

    def get_index_fields(self) -> list[SearchableField]:
        """This function returns the index fields for rag document.

        Returns:
            list[SearchableField]: The index fields for rag document"""

        fields = [
            SimpleField(name="Id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(
                name="Title", type=SearchFieldDataType.String, filterable=True
            ),
            SearchableField(
                name="ChunkId",
                type=SearchFieldDataType.String,
                key=True,
                analyzer_name="keyword",
            ),
            SearchableField(
                name="Chunk",
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
            SearchField(
                name="ChunkEmbedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=self.environment.open_ai_embedding_dimensions,
                vector_search_profile_name=self.vector_search_profile_name,
            ),
            SearchableField(
                name="SourceUri",
                type=SearchFieldDataType.String,
                sortable=True,
                filterable=True,
                facetable=True,
            ),
            ComplexField(
                name="ChunkFigures",
                collection=True,
                fields=[
                    SimpleField(
                        name="FigureId",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    SimpleField(
                        name="Caption",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    SimpleField(
                        name="PageNumber",
                        type=SearchFieldDataType.Int64,
                        filterable=True,
                    ),
                    SimpleField(
                        name="Uri",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    SimpleField(
                        name="Description",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    SimpleField(
                        name="Data",
                        type=SearchFieldDataType.String,
                        filterable=False,
                    ),
                ],
            ),
            SimpleField(
                name="DateLastModified",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
            ),
        ]

        if self.enable_page_by_chunking:
            fields.extend(
                [
                    SearchableField(
                        name="PageNumber",
                        type=SearchFieldDataType.Int64,
                        sortable=True,
                        filterable=True,
                        facetable=True,
                    )
                ]
            )

        return fields

    def get_semantic_search(self) -> SemanticSearch:
        """This function returns the semantic search configuration for rag document

        Returns:
            SemanticSearch: The semantic search configuration"""

        semantic_config = SemanticConfiguration(
            name=self.semantic_config_name,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="Title"),
                content_fields=[SemanticField(field_name="Chunk")],
                keywords_fields=[
                    SemanticField(field_name="Sections"),
                ],
            ),
        )

        semantic_search = SemanticSearch(configurations=[semantic_config])

        return semantic_search

    def get_skills(self) -> list:
        """Get the skillset for the indexer.

        Returns:
            list: The skillsets  used in the indexer"""

        adi_skill = self.get_adi_skill(self.enable_page_by_chunking)

        text_split_skill = self.get_text_split_skill(
            "/document", "/document/extracted_content/content"
        )

        mark_up_cleaner_skill = self.get_mark_up_cleaner_skill(
            "/document/chunks/*", "/document/chunks/*/content"
        )

        embedding_skill = self.get_vector_skill(
            "/document/chunks/*", "/document/chunks/*/cleaned_chunk"
        )

        if self.enable_page_by_chunking:
            skills = [
                adi_skill,
                mark_up_cleaner_skill,
                embedding_skill,
            ]
        else:
            skills = [
                adi_skill,
                text_split_skill,
                mark_up_cleaner_skill,
                embedding_skill,
            ]

        return skills

    def get_index_projections(self) -> SearchIndexerIndexProjection:
        """This function returns the index projections for rag document."""
        mappings = [
            InputFieldMappingEntry(name="Chunk", source="/document/chunks/*/chunk"),
            InputFieldMappingEntry(
                name="ChunkEmbedding",
                source="/document/chunks/*/vector",
            ),
            InputFieldMappingEntry(name="Title", source="/document/Title"),
            InputFieldMappingEntry(name="SourceUri", source="/document/SourceUri"),
            InputFieldMappingEntry(
                name="Sections", source="/document/chunks/*/sections"
            ),
            InputFieldMappingEntry(
                name="Figures",
                source_context="/document/chunks/*/chunk_figures/*",
            ),
            InputFieldMappingEntry(
                name="DateLastModified", source="/document/DateLastModified"
            ),
        ]

        if self.enable_page_by_chunking:
            mappings.extend(
                [
                    InputFieldMappingEntry(
                        name="PageNumber", source="/document/chunks/*/pageNumber"
                    )
                ]
            )

        index_projections = SearchIndexerIndexProjection(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.index_name,
                    parent_key_field_name="Id",
                    source_context="/document/chunks/*",
                    mappings=mappings,
                ),
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
            ),
        )

        return index_projections

    def get_indexer(self) -> SearchIndexer:
        """This function returns the indexer for rag document.

        Returns:
            SearchIndexer: The indexer for rag document"""

        # Only place on schedule if it is not a test deployment
        if self.test:
            schedule = None
            batch_size = 4
        else:
            schedule = {"interval": "PT15M"}
            batch_size = 16

        if self.environment.use_private_endpoint:
            execution_environment = IndexerExecutionEnvironment.PRIVATE
        else:
            execution_environment = IndexerExecutionEnvironment.STANDARD

        indexer_parameters = IndexingParameters(
            batch_size=batch_size,
            configuration=IndexingParametersConfiguration(
                data_to_extract=BlobIndexerDataToExtract.STORAGE_METADATA,
                query_timeout=None,
                execution_environment=execution_environment,
                fail_on_unprocessable_document=False,
                fail_on_unsupported_content_type=False,
                index_storage_metadata_only_for_oversized_documents=True,
                indexed_file_name_extensions=".pdf,.pptx,.docx,.xlsx,.txt,.png,.jpg,.jpeg",
                parsing_mode=self.parsing_mode,
            ),
            max_failed_items=5,
        )

        indexer = SearchIndexer(
            name=self.indexer_name,
            description="Indexer to index documents and generate embeddings",
            skillset_name=self.skillset_name,
            target_index_name=self.index_name,
            data_source_name=self.data_source_name,
            schedule=schedule,
            field_mappings=[
                FieldMapping(
                    source_field_name="metadata_storage_name", target_field_name="Title"
                ),
                FieldMapping(
                    source_field_name="metadata_storage_path",
                    target_field_name="SourceUri",
                ),
                FieldMapping(
                    source_field_name="metadata_storage_last_modified",
                    target_field_name="DateLastModified",
                ),
            ],
            parameters=indexer_parameters,
        )

        return indexer
