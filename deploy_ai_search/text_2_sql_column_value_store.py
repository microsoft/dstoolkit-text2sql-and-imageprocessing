# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    SearchableField,
    SearchIndexer,
    FieldMapping,
    SimpleField,
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
        self.indexer_type = IndexerType.TEXT_2_SQL_COLUMN_VALUE_STORE
        self.database_engine = DatabaseEngine[
            os.environ["Text2Sql__DatabaseEngine"].upper()
        ]
        super().__init__(suffix, rebuild)

    @property
    def excluded_fields_for_database_engine(self):
        """A method to get the excluded fields for the database engine."""

        all_engine_specific_fields = ["Warehouse", "Database", "Catalog"]
        if self.database_engine == DatabaseEngine.SNOWFLAKE:
            engine_specific_fields = ["Warehouse", "Database"]
        elif self.database_engine == DatabaseEngine.TSQL:
            engine_specific_fields = ["Database"]
        elif self.database_engine == DatabaseEngine.DATABRICKS:
            engine_specific_fields = ["Catalog"]

        return [
            field
            for field in all_engine_specific_fields
            if field not in engine_specific_fields
        ]

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
            SimpleField(
                name="Entity",
                type=SearchFieldDataType.String,
            ),
            SimpleField(
                name="Database",
                type=SearchFieldDataType.String,
            ),
            SimpleField(
                name="Warehouse",
                type=SearchFieldDataType.String,
            ),
            SimpleField(
                name="Catalog",
                type=SearchFieldDataType.String,
            ),
            SimpleField(
                name="Column",
                type=SearchFieldDataType.String,
            ),
            SearchableField(
                name="Value",
                type=SearchFieldDataType.String,
                hidden=False,
            ),
            SimpleField(
                name="Synonyms", type=SearchFieldDataType.String, collection=True
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
            if field.name not in self.excluded_fields_for_database_engine
        ]

        return fields

    def get_skills(self) -> list:
        """Get the skillset for the indexer.

        Returns:
            list: The skillsets  used in the indexer"""

        skills = []

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
                indexed_file_name_extensions=".jsonl",
                parsing_mode=BlobIndexerParsingMode.JSON_LINES,
            ),
            max_failed_items=5,
        )

        indexer = SearchIndexer(
            name=self.indexer_name,
            description="Indexer to column values",
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
                    source_field_name="/document/Database",
                    target_field_name="Database",
                ),
                FieldMapping(
                    source_field_name="/document/Warehouse",
                    target_field_name="Warehouse",
                ),
                FieldMapping(
                    source_field_name="/document/Column",
                    target_field_name="Column",
                ),
                FieldMapping(
                    source_field_name="/document/Value",
                    target_field_name="Value",
                ),
                FieldMapping(
                    source_field_name="/document/Synonyms",
                    target_field_name="Synonyms",
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
            not in self.excluded_fields_for_database_engine
        ]

        return indexer
