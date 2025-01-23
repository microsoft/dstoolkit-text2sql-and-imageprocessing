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
import os
from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.factory import ConnectorFactory


class Text2SqlSchemaStoreAISearch(AISearch):
    """This class is used to deploy the sql index."""

    def __init__(
        self,
        suffix: str | None = None,
        rebuild: bool | None = False,
        single_data_dictionary_file: bool | None = False,
    ):
        """Initialize the Text2SqlAISearch class. This class implements the deployment of the sql index.

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """
        self.indexer_type = IndexerType.TEXT_2_SQL_SCHEMA_STORE
        super().__init__(suffix, rebuild)
        self.database_engine = DatabaseEngine[
            os.environ["Text2Sql__DatabaseEngine"].upper()
        ]

        self.database_connector = ConnectorFactory.get_database_connector()

        if single_data_dictionary_file:
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
                name="FQN",
                type=SearchFieldDataType.String,
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
                name="Schema",
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
                name="Catalog",
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
                        name="SampleValues",
                        type=SearchFieldDataType.String,
                        collection=True,
                        searchable=False,
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
            SearchableField(
                name="CompleteEntityRelationshipsGraph",
                type=SearchFieldDataType.String,
                collection=True,
            ),
            SimpleField(
                name="DateLastModified",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
            ),
        ]

        # Remove fields that are not supported by the database engine
        fields = [
            field
            for field in fields
            if field.name not in self.database_connector.excluded_engine_specific_fields
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
                    source_field_name="/document/FQN",
                    target_field_name="Id",
                    mapping_function=FieldMappingFunction(
                        name="base64Encode",
                        parameters={"useHttpServerUtilityUrlTokenEncode": False},
                    ),
                ),
                FieldMapping(
                    source_field_name="/document/FQN", target_field_name="FQN"
                ),
                FieldMapping(
                    source_field_name="/document/EntityName",
                    target_field_name="EntityName",
                ),
                FieldMapping(
                    source_field_name="/document/Entity", target_field_name="Entity"
                ),
                FieldMapping(
                    source_field_name="/document/Schema", target_field_name="Schema"
                ),
                FieldMapping(
                    source_field_name="/document/Catalog", target_field_name="Catalog"
                ),
                FieldMapping(
                    source_field_name="/document/Database",
                    target_field_name="Database",
                ),
                FieldMapping(
                    source_field_name="/document/Warehouse",
                    target_field_name="Warehouse",
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
                    source_field_name="/document/EntityRelationships",
                    target_field_name="EntityRelationships",
                ),
                FieldMapping(
                    source_field_name="/document/CompleteEntityRelationshipsGraph/*",
                    target_field_name="CompleteEntityRelationshipsGraph",
                ),
                FieldMapping(
                    source_field_name="/document/DateLastModified",
                    target_field_name="DateLastModified",
                ),
            ],
            parameters=indexer_parameters,
        )

        # Remove fields that are not supported by the database engine
        indexer.output_field_mappings = [
            field_mapping
            for field_mapping in indexer.output_field_mappings
            if field_mapping.target_field_name
            not in self.database_connector.excluded_engine_specific_fields
        ]

        return indexer
