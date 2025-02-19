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


class ImageProcessingAISearch(AISearch):
    """This class is used to deploy the rag document index."""

    def __init__(
        self,
        suffix: str | None = None,
        rebuild: bool | None = False,
        enable_page_by_chunking=False,
    ):
        """Initialize the ImageProcessingAISearch class. This class implements the deployment of the rag document index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.IMAGE_PROCESSING
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
            SimpleField(
                name="PageNumber",
                type=SearchFieldDataType.Int64,
                sortable=True,
                filterable=True,
                facetable=True,
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

        layout_skill = self.get_layout_analysis_skill(self.enable_page_by_chunking)

        figure_skill = self.get_figure_analysis_skill(self.enable_page_by_chunking)

        merger_skill = self.get_layout_and_figure_merger_skill(
            self.enable_page_by_chunking
        )

        mark_up_cleaner_skill = self.get_mark_up_cleaner_skill(
            self.enable_page_by_chunking
        )

        if self.enable_page_by_chunking:
            embedding_skill = self.get_vector_skill(
                "/document/page_wise_layout/*",
                "/document/page_wise_layout/*/final_cleaned_text",
            )
        else:
            embedding_skill = self.get_vector_skill(
                "/document/chunk_mark_ups/*",
                "/document/chunk_mark_ups/*/final_cleaned_text",
            )

        if self.enable_page_by_chunking:
            skills = [
                layout_skill,
                figure_skill,
                merger_skill,
                mark_up_cleaner_skill,
                embedding_skill,
            ]
        else:
            semantic_chunker_skill = self.get_semantic_chunker_skill()
            skills = [
                layout_skill,
                figure_skill,
                merger_skill,
                semantic_chunker_skill,
                mark_up_cleaner_skill,
                embedding_skill,
            ]

        return skills

    def get_index_projections(self) -> SearchIndexerIndexProjection:
        """This function returns the index projections for rag document."""

        if self.enable_page_by_chunking:
            source_context = "/document/page_wise_layout/*"
            mappings = [
                InputFieldMappingEntry(
                    name="Chunk", source="/document/page_wise_layout/*/final_mark_up"
                ),
                InputFieldMappingEntry(
                    name="ChunkEmbedding",
                    source="/document/page_wise_layout/*/vector",
                ),
                InputFieldMappingEntry(name="Title", source="/document/Title"),
                InputFieldMappingEntry(name="SourceUri", source="/document/SourceUri"),
                InputFieldMappingEntry(
                    name="Sections",
                    source="/document/page_wise_layout/*/final_sections",
                ),
                InputFieldMappingEntry(
                    name="ChunkFigures",
                    source="/document/page_wise_layout/*/final_chunk_figures/*",
                ),
                InputFieldMappingEntry(
                    name="DateLastModified", source="/document/DateLastModified"
                ),
                InputFieldMappingEntry(
                    name="PageNumber",
                    source="/document/page_wise_layout/*/final_page_number",
                ),
            ]
        else:
            source_context = "/document/chunk_mark_ups/*"
            mappings = [
                InputFieldMappingEntry(
                    name="Chunk", source="/document/chunk_mark_ups/*/final_mark_up"
                ),
                InputFieldMappingEntry(
                    name="ChunkEmbedding",
                    source="/document/chunk_mark_ups/*/vector",
                ),
                InputFieldMappingEntry(name="Title", source="/document/Title"),
                InputFieldMappingEntry(name="SourceUri", source="/document/SourceUri"),
                InputFieldMappingEntry(
                    name="Sections", source="/document/chunk_mark_ups/*/final_sections"
                ),
                InputFieldMappingEntry(
                    name="ChunkFigures",
                    source="/document/chunk_mark_ups/*/final_chunk_figures/*",
                ),
                InputFieldMappingEntry(
                    name="DateLastModified", source="/document/DateLastModified"
                ),
                InputFieldMappingEntry(
                    name="PageNumber",
                    source="/document/chunk_mark_ups/*/final_page_number",
                ),
            ]

        index_projections = SearchIndexerIndexProjection(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.index_name,
                    parent_key_field_name="Id",
                    source_context=source_context,
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
            batch_size = 1
        else:
            schedule = {"interval": "PT15M"}
            batch_size = 2

        if self.environment.use_private_endpoint:
            execution_environment = IndexerExecutionEnvironment.PRIVATE
        else:
            execution_environment = IndexerExecutionEnvironment.STANDARD

        indexer_parameters = IndexingParameters(
            batch_size=batch_size,
            configuration=IndexingParametersConfiguration(
                data_to_extract=BlobIndexerDataToExtract.ALL_METADATA,
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
