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
    SearchIndexerIndexProjections,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SimpleField,
    BlobIndexerDataToExtract,
    IndexerExecutionEnvironment,
)
from ai_search import AISearch
from ai_search_with_adi.ai_search.environment import (
    get_search_embedding_model_dimensions,
    IndexerType,
)


class RagDocumentsAISearch(AISearch):
    """This class is used to deploy the rag document index."""

    def __init__(
        self,
        endpoint,
        credential,
        suffix=None,
        rebuild=False,
        enable_page_by_chunking=False,
    ):
        super().__init__(endpoint, credential, suffix, rebuild)

        self.indexer_type = IndexerType.RAG_DOCUMENTS
        if enable_page_by_chunking is not None:
            self.enable_page_by_chunking = enable_page_by_chunking
        else:
            self.enable_page_by_chunking = False

    def get_index_fields(self) -> list[SearchableField]:
        """This function returns the index fields for inquiry document.

        Returns:
            list[SearchableField]: The index fields for inquiry document"""

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
                vector_search_dimensions=get_search_embedding_model_dimensions(
                    self.indexer_type
                ),
                vector_search_profile_name=self.vector_search_profile_name,
            ),
            SearchableField(
                name="Keywords", type=SearchFieldDataType.String, collection=True
            ),
            SearchableField(
                name="SourceUri",
                type=SearchFieldDataType.String,
                sortable=True,
                filterable=True,
                facetable=True,
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
        """This function returns the semantic search configuration for inquiry document

        Returns:
            SemanticSearch: The semantic search configuration"""

        semantic_config = SemanticConfiguration(
            name=self.semantic_config_name,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="Title"),
                content_fields=[SemanticField(field_name="Chunk")],
                keywords_fields=[
                    SemanticField(field_name="Keywords"),
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

        pre_embedding_cleaner_skill = self.get_pre_embedding_cleaner_skill(
            "/document/pages/*", "/document/pages/*", self.enable_page_by_chunking
        )

        key_phrase_extraction_skill = self.get_key_phrase_extraction_skill(
            "/document/pages/*", "/document/pages/*/cleaned_chunk"
        )

        embedding_skill = self.get_vector_skill(
            "/document/pages/*", "/document/pages/*/cleaned_chunk"
        )

        if self.enable_page_by_chunking:
            skills = [
                adi_skill,
                pre_embedding_cleaner_skill,
                key_phrase_extraction_skill,
                embedding_skill,
            ]
        else:
            skills = [
                adi_skill,
                text_split_skill,
                pre_embedding_cleaner_skill,
                key_phrase_extraction_skill,
                embedding_skill,
            ]

        return skills

    def get_index_projections(self) -> SearchIndexerIndexProjections:
        """This function returns the index projections for inquiry document."""
        mappings = [
            InputFieldMappingEntry(name="Chunk", source="/document/pages/*/chunk"),
            InputFieldMappingEntry(
                name="ChunkEmbedding",
                source="/document/pages/*/vector",
            ),
            InputFieldMappingEntry(name="Title", source="/document/Title"),
            InputFieldMappingEntry(name="SourceUri", source="/document/SourceUri"),
            InputFieldMappingEntry(
                name="Keywords", source="/document/pages/*/keywords"
            ),
            InputFieldMappingEntry(
                name="Sections", source="/document/pages/*/sections"
            ),
        ]

        if self.enable_page_by_chunking:
            mappings.extend(
                [
                    InputFieldMappingEntry(
                        name="PageNumber", source="/document/pages/*/page_number"
                    )
                ]
            )

        index_projections = SearchIndexerIndexProjections(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.index_name,
                    parent_key_field_name="Id",
                    source_context="/document/pages/*",
                    mappings=mappings,
                ),
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
            ),
        )

        return index_projections

    def get_indexer(self) -> SearchIndexer:
        """This function returns the indexer for inquiry document.

        Returns:
            SearchIndexer: The indexer for inquiry document"""
        if self.test:
            schedule = None
            batch_size = 4
        else:
            schedule = {"interval": "PT15M"}
            batch_size = 16

        indexer_parameters = IndexingParameters(
            batch_size=batch_size,
            configuration=IndexingParametersConfiguration(
                data_to_extract=BlobIndexerDataToExtract.ALL_METADATA,
                query_timeout=None,
                execution_environment=IndexerExecutionEnvironment.PRIVATE,
                fail_on_unprocessable_document=False,
                fail_on_unsupported_content_type=False,
                index_storage_metadata_only_for_oversized_documents=True,
                indexed_file_name_extensions=".pdf,.pptx,.docx,.xlsx,.txt",
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
            ],
            parameters=indexer_parameters,
        )

        return indexer
