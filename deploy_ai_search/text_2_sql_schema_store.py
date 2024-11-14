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
    FieldMappingFunction,
)
from ai_search import AISearch
from environment import (
    IndexerType,
)


class Text2SqlSchemaStoreAISearch(AISearch):
    """This class is used to deploy the sql index."""

    def __init__(
        self,
        suffix: str | None = None,
        rebuild: bool | None = False,
        single_data_dictionary: bool | None = False,
    ):
        """Initialize the Text2SqlAISearch class. This class implements the deployment of the sql index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.TEXT_2_SQL_SCHEMA_STORE
        super().__init__(suffix, rebuild)

        if single_data_dictionary:
            self.parsing_mode = BlobIndexerParsingMode.JSON_ARRAY
        else:
            self.parsing_mode = BlobIndexerParsingMode.JSON

    def get_index_fields(self) -> list[SearchableField]:
        """This function returns the index fields for sql index.

        Returns:
            list[SearchableField]: The index fields for sql index"""

        fields = [
            SimpleField(
                name="Id",
                type=SearchFieldDataType.String,
                key=True,
                analyzer_name="keyword",
            ),
            SearchableField(
                name="EntityName", type=SearchFieldDataType.String, filterable=True
            ),
            SearchableField(
                name="Entity",
                type=SearchFieldDataType.String,
                analyzer_name="keyword",
            ),
            SearchableField(
                name="Database",
                type=SearchFieldDataType.String,
            ),
            SearchableField(
                name="Warehouse",
                type=SearchFieldDataType.String,
            ),
            SearchableField(
                name="Definition",
                type=SearchFieldDataType.String,
                sortable=False,
                filterable=False,
                facetable=False,
            ),
            SearchField(
                name="DefinitionEmbedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=self.environment.open_ai_embedding_dimensions,
                vector_search_profile_name=self.vector_search_profile_name,
                hidden=True,
            ),
            ComplexField(
                name="Columns",
                collection=True,
                fields=[
                    SearchableField(name="Name", type=SearchFieldDataType.String),
                    SearchableField(name="Definition", type=SearchFieldDataType.String),
                    SearchableField(name="DataType", type=SearchFieldDataType.String),
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
                    SearchableField(
                        name="JoinableEntities",
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
                # This is needed to enable semantic searching against the column names as complex field types are not used.
            ),
            SearchableField(
                name="ColumnDefinitions",
                type=SearchFieldDataType.String,
                collection=True,
                hidden=True,
                # This is needed to enable semantic searching against the column names as complex field types are not used.
            ),
            ComplexField(
                name="EntityRelationships",
                collection=True,
                fields=[
                    SearchableField(
                        name="ForeignEntity",
                        type=SearchFieldDataType.String,
                    ),
                    ComplexField(
                        name="ForeignKeys",
                        collection=True,
                        fields=[
                            SearchableField(
                                name="Column", type=SearchFieldDataType.String
                            ),
                            SearchableField(
                                name="ForeignColumn", type=SearchFieldDataType.String
                            ),
                        ],
                    ),
                ],
            ),
            SimpleField(
                name="CompleteEntityRelationshipGraph",
                type=SearchFieldDataType.String,
                collection=True,
            ),
            SimpleField(
                name="DateLastModified",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
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
                    SemanticField(field_name="Definition"),
                    SemanticField(field_name="ColumnDefinitions"),
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
            "/document", "/document/Definition", target_name="DefinitionEmbedding"
        )

        skills = [embedding_skill]

        return skills

    def get_indexer(self) -> SearchIndexer:
        """This function returns the indexer for sql.

        Returns:
            SearchIndexer: The indexer for sql"""

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
                indexed_file_name_extensions=".json",
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
            field_mappings=[
                FieldMapping(
                    source_field_name="metadata_storage_last_modified",
                    target_field_name="DateLastModified",
                )
            ],
            output_field_mappings=[
                FieldMapping(
                    source_field_name="/document/Entity",
                    target_field_name="Id",
                    mapping_function=FieldMappingFunction(
                        name="base64Encode",
                        parameters={"useHttpServerUtilityUrlTokenEncode": False},
                    ),
                ),
                FieldMapping(
                    source_field_name="/document/Entity", target_field_name="Entity"
                ),
                FieldMapping(
                    source_field_name="/document/EntityName",
                    target_field_name="EntityName",
                ),
                FieldMapping(
                    source_field_name="/document/Definition",
                    target_field_name="Definition",
                ),
                FieldMapping(
                    source_field_name="/document/DefinitionEmbedding",
                    target_field_name="DefinitionEmbedding",
                ),
                FieldMapping(
                    source_field_name="/document/Columns",
                    target_field_name="Columns",
                ),
                FieldMapping(
                    source_field_name="/document/Columns/*/Name",
                    target_field_name="ColumnNames",
                ),
                FieldMapping(
                    source_field_name="/document/Columns/*/Definition",
                    target_field_name="ColumnDefinitions",
                ),
                FieldMapping(
                    source_field_name="/document/ImmediateEntityRelationships",
                    target_field_name="ImmediateEntityRelationships",
                ),
                FieldMapping(
                    source_field_name="/document/CompleteEntityRelationships",
                    target_field_name="CompleteEntityRelationships",
                ),
                FieldMapping(
                    source_field_name="/document/DateLastModified",
                    target_field_name="DateLastModified",
                ),
            ],
            parameters=indexer_parameters,
        )

        return indexer
