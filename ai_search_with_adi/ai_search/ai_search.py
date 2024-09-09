# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC, abstractmethod
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticSearch,
    NativeBlobSoftDeleteDeletionDetectionPolicy,
    HighWaterMarkChangeDetectionPolicy,
    WebApiSkill,
    CustomVectorizer,
    CustomWebApiParameters,
    SearchIndexer,
    SearchIndexerSkillset,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataSourceType,
    SearchIndexerDataUserAssignedIdentity,
    OutputFieldMappingEntry,
    InputFieldMappingEntry,
    SynonymMap,
    DocumentExtractionSkill,
    OcrSkill,
    MergeSkill,
    ConditionalSkill,
    SplitSkill,
)
from azure.core.exceptions import HttpResponseError
from azure.search.documents.indexes import SearchIndexerClient, SearchIndexClient
from ai_search_with_adi.ai_search.environment import (
    get_fq_blob_connection_string,
    get_blob_container_name,
    get_custom_skill_function_url,
    get_managed_identity_fqname,
    get_function_app_authresourceid,
    IndexerType,
)


class AISearch(ABC):
    def __init__(
        self,
        endpoint: str,
        credential,
        suffix: str | None = None,
        rebuild: bool | None = False,
    ):
        """Initialize the AI search class

        Args:
            endpoint (str): The search endpoint
            credential (AzureKeyCredential): The search credential"""
        self.indexer_type = None

        if rebuild is not None:
            self.rebuild = rebuild
        else:
            self.rebuild = False

        if suffix is None:
            self.suffix = ""
            self.test = False
        else:
            self.suffix = f"-{suffix}-test"
            self.test = True

        self._search_indexer_client = SearchIndexerClient(endpoint, credential)
        self._search_index_client = SearchIndexClient(endpoint, credential)

    @property
    def indexer_name(self):
        """Get the indexer name for the indexer."""
        return f"{str(self.indexer_type.value)}-indexer{self.suffix}"

    @property
    def skillset_name(self):
        """Get the skillset name for the indexer."""
        return f"{str(self.indexer_type.value)}-skillset{self.suffix}"

    @property
    def semantic_config_name(self):
        """Get the semantic config name for the indexer."""
        return f"{str(self.indexer_type.value)}-semantic-config{self.suffix}"

    @property
    def index_name(self):
        """Get the index name for the indexer."""
        return f"{str(self.indexer_type.value)}-index{self.suffix}"

    @property
    def data_source_name(self):
        """Get the data source name for the indexer."""
        blob_container_name = get_blob_container_name(self.indexer_type)
        return f"{blob_container_name}-data-source{self.suffix}"

    @property
    def vector_search_profile_name(self):
        """Get the vector search profile name for the indexer."""
        return (
            f"{str(self.indexer_type.value)}-compass-vector-search-profile{self.suffix}"
        )

    @property
    def vectorizer_name(self):
        """Get the vectorizer name."""
        return f"{str(self.indexer_type.value)}-compass-vectorizer{self.suffix}"

    @property
    def algorithm_name(self):
        """Gtt the algorithm name"""

        return f"{str(self.indexer_type.value)}-hnsw-algorithm{self.suffix}"

    @abstractmethod
    def get_index_fields(self) -> list[SearchableField]:
        """Get the index fields for the indexer.

        Returns:
            list[SearchableField]: The index fields"""

    @abstractmethod
    def get_semantic_search(self) -> SemanticSearch:
        """Get the semantic search configuration for the indexer.

        Returns:
            SemanticSearch: The semantic search configuration"""

    @abstractmethod
    def get_skills(self):
        """Get the skillset for the indexer."""

    @abstractmethod
    def get_indexer(self) -> SearchIndexer:
        """Get the indexer for the indexer."""

    def get_index_projections(self):
        """Get the index projections for the indexer."""
        return None

    def get_synonym_map_names(self):
        """Get the synonym map names for the indexer."""
        return []

    def get_user_assigned_managed_identity(
        self,
    ) -> SearchIndexerDataUserAssignedIdentity:
        """Get user assigned managed identity details"""

        user_assigned_identity = SearchIndexerDataUserAssignedIdentity(
            user_assigned_identity=get_managed_identity_fqname()
        )
        return user_assigned_identity

    def get_data_source(self) -> SearchIndexerDataSourceConnection:
        """Get the data source for the indexer."""

        if self.indexer_type == IndexerType.BUSINESS_GLOSSARY:
            data_deletion_detection_policy = None
        else:
            data_deletion_detection_policy = (
                NativeBlobSoftDeleteDeletionDetectionPolicy()
            )

        data_change_detection_policy = HighWaterMarkChangeDetectionPolicy(
            high_water_mark_column_name="metadata_storage_last_modified"
        )

        container = SearchIndexerDataContainer(
            name=get_blob_container_name(self.indexer_type)
        )

        data_source_connection = SearchIndexerDataSourceConnection(
            name=self.data_source_name,
            type=SearchIndexerDataSourceType.AZURE_BLOB,
            connection_string=get_fq_blob_connection_string(),
            container=container,
            data_change_detection_policy=data_change_detection_policy,
            data_deletion_detection_policy=data_deletion_detection_policy,
            identity=self.get_user_assigned_managed_identity(),
        )

        return data_source_connection

    def get_compass_vector_custom_skill(
        self, context, source, target_name="vector"
    ) -> WebApiSkill:
        """Get the custom skill for compass.

        Args:
        -----
            context (str): The context of the skill
            source (str): The source of the skill
            target_name (str): The target name of the skill

        Returns:
        --------
            WebApiSkill: The custom skill for compass"""

        if self.test:
            batch_size = 2
            degree_of_parallelism = 2
        else:
            batch_size = 4
            degree_of_parallelism = 8

        embedding_skill_inputs = [
            InputFieldMappingEntry(name="text", source=source),
        ]
        embedding_skill_outputs = [
            OutputFieldMappingEntry(name="vector", target_name=target_name)
        ]
        # Limit the number of documents to be processed in parallel to avoid timing out on compass api
        embedding_skill = WebApiSkill(
            name="Compass Connector API",
            description="Skill to generate embeddings via compass API connector",
            context=context,
            uri=get_custom_skill_function_url("compass"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=embedding_skill_inputs,
            outputs=embedding_skill_outputs,
            auth_resource_id=get_function_app_authresourceid(),
            auth_identity=self.get_user_assigned_managed_identity(),
        )

        return embedding_skill

    def get_pre_embedding_cleaner_skill(
        self, context, source, chunk_by_page=False, target_name="cleaned_chunk"
    ) -> WebApiSkill:
        """Get the custom skill for data cleanup.

        Args:
        -----
            context (str): The context of the skill
            inputs (List[InputFieldMappingEntry]): The inputs of the skill
            outputs (List[OutputFieldMappingEntry]): The outputs of the skill

        Returns:
        --------
            WebApiSkill: The custom skill for data cleanup"""

        if self.test:
            batch_size = 2
            degree_of_parallelism = 2
        else:
            batch_size = 16
            degree_of_parallelism = 16

        pre_embedding_cleaner_skill_inputs = [
            InputFieldMappingEntry(name="chunk", source=source)
        ]

        pre_embedding_cleaner_skill_outputs = [
            OutputFieldMappingEntry(name="cleaned_chunk", target_name=target_name),
            OutputFieldMappingEntry(name="chunk", target_name="chunk"),
            OutputFieldMappingEntry(name="section", target_name="eachsection"),
        ]

        if chunk_by_page:
            pre_embedding_cleaner_skill_outputs.extend(
                [
                    OutputFieldMappingEntry(name="page_number", target_name="page_no"),
                ]
            )

        pre_embedding_cleaner_skill = WebApiSkill(
            name="Pre Embedding Cleaner Skill",
            description="Skill to clean the data before sending to embedding",
            context=context,
            uri=get_custom_skill_function_url("pre_embedding_cleaner"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=pre_embedding_cleaner_skill_inputs,
            outputs=pre_embedding_cleaner_skill_outputs,
            auth_resource_id=get_function_app_authresourceid(),
            auth_identity=self.get_user_assigned_managed_identity(),
        )

        return pre_embedding_cleaner_skill

    def get_text_split_skill(self, context, source) -> SplitSkill:
        """Get the skill for text split.

        Args:
        -----
            context (str): The context of the skill
            inputs (List[InputFieldMappingEntry]): The inputs of the skill
            outputs (List[OutputFieldMappingEntry]): The outputs of the skill

        Returns:
        --------
            splitSKill: The skill for text split"""

        text_split_skill = SplitSkill(
            name="Text Split Skill",
            description="Skill to split the text before sending to embedding",
            context=context,
            text_split_mode="pages",
            maximum_page_length=2000,
            page_overlap_length=500,
            inputs=[InputFieldMappingEntry(name="text", source=source)],
            outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
        )

        return text_split_skill

    
    def get_adi_skill(self, chunk_by_page=False) -> WebApiSkill:
        """Get the custom skill for adi.

        Returns:
        --------
            WebApiSkill: The custom skill for adi"""

        if self.test:
            batch_size = 1
            degree_of_parallelism = 4
        else:
            batch_size = 1
            degree_of_parallelism = 16

        if chunk_by_page:
            output = [
                OutputFieldMappingEntry(name="extracted_content", target_name="pages")
            ]
        else:
            output = [
                OutputFieldMappingEntry(
                    name="extracted_content", target_name="extracted_content"
                )
            ]

        adi_skill = WebApiSkill(
            name="ADI Skill",
            description="Skill to generate ADI",
            context="/document",
            uri=get_custom_skill_function_url("adi"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            http_headers={"chunk_by_page": chunk_by_page},
            inputs=[
                InputFieldMappingEntry(
                    name="source", source="/document/metadata_storage_path"
                )
            ],
            outputs=output,
            auth_resource_id=get_function_app_authresourceid(),
            auth_identity=self.get_user_assigned_managed_identity(),
        )

        return adi_skill

    def get_excel_skill(self) -> WebApiSkill:
        """Get the custom skill for adi.

        Returns:
        --------
            WebApiSkill: The custom skill for adi"""

        if self.test:
            batch_size = 1
            degree_of_parallelism = 4
        else:
            batch_size = 1
            degree_of_parallelism = 8

        output = [
            OutputFieldMappingEntry(name="extracted_content", target_name="pages")
        ]

        xlsx_skill = WebApiSkill(
            name="XLSX Skill",
            description="Skill to generate Markdown from XLSX",
            context="/document",
            uri=get_custom_skill_function_url("xlsx"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            http_headers={},
            inputs=[
                InputFieldMappingEntry(
                    name="source", source="/document/metadata_storage_path"
                )
            ],
            outputs=output,
            auth_resource_id=get_function_app_authresourceid(),
            auth_identity=self.get_user_assigned_managed_identity(),
        )

        return xlsx_skill

    def get_key_phrase_extraction_skill(self, context, source) -> WebApiSkill:
        """Get the key phrase extraction skill.

        Args:
        -----
            context (str): The context of the skill
            source (str): The source of the skill

        Returns:
        --------
            WebApiSkill: The key phrase extraction skill"""

        if self.test:
            batch_size = 4
            degree_of_parallelism = 4
        else:
            batch_size = 16
            degree_of_parallelism = 16

        keyphrase_extraction_skill_inputs = [
            InputFieldMappingEntry(name="text", source=source),
        ]
        keyphrase_extraction__skill_outputs = [
            OutputFieldMappingEntry(name="keyPhrases", target_name="keywords")
        ]
        key_phrase_extraction_skill = WebApiSkill(
            name="Key phrase extraction API",
            description="Skill to extract keyphrases",
            context=context,
            uri=get_custom_skill_function_url("keyphraseextraction"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=keyphrase_extraction_skill_inputs,
            outputs=keyphrase_extraction__skill_outputs,
            auth_resource_id=get_function_app_authresourceid(),
            auth_identity=self.get_user_assigned_managed_identity(),
        )

        return key_phrase_extraction_skill

    def get_document_extraction_skill(self, context, source) -> DocumentExtractionSkill:
        """Get the document extraction utility skill.

        Args:
        -----
            context (str): The context of the skill
            source (str): The source of the skill

        Returns:
        --------
            DocumentExtractionSkill: The document extraction utility skill"""

        doc_extraction_skill = DocumentExtractionSkill(
            description="Extraction skill to extract content from office docs like excel, ppt, doc etc",
            context=context,
            inputs=[InputFieldMappingEntry(name="file_data", source=source)],
            outputs=[
                OutputFieldMappingEntry(
                    name="content", target_name="extracted_content"
                ),
                OutputFieldMappingEntry(
                    name="normalized_images", target_name="extracted_normalized_images"
                ),
            ],
        )

        return doc_extraction_skill

    def get_ocr_skill(self, context, source) -> OcrSkill:
        """Get the ocr utility skill
        Args:
        -----
            context (str): The context of the skill
            source (str): The source of the skill

        Returns:
        --------
            OcrSkill: The ocr skill"""

        if self.test:
            batch_size = 2
            degree_of_parallelism = 2
        else:
            batch_size = 2
            degree_of_parallelism = 2

        ocr_skill_inputs = [
            InputFieldMappingEntry(name="image", source=source),
        ]
        ocr__skill_outputs = [OutputFieldMappingEntry(name="text", target_name="text")]
        ocr_skill = WebApiSkill(
            name="ocr API",
            description="Skill to extract text from images",
            context=context,
            uri=get_custom_skill_function_url("ocr"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=ocr_skill_inputs,
            outputs=ocr__skill_outputs,
            auth_resource_id=get_function_app_authresourceid(),
            auth_identity=self.get_user_assigned_managed_identity(),
        )

        return ocr_skill

    def get_merge_skill(self, context, source) -> MergeSkill:
        """Get the merge
        Args:
        -----
            context (str): The context of the skill
            source (array): The source of the skill

        Returns:
        --------
            mergeSkill: The merge skill"""

        merge_skill = MergeSkill(
            description="Merge skill for combining OCR'd and regular text",
            context=context,
            inputs=[
                InputFieldMappingEntry(name="text", source=source[0]),
                InputFieldMappingEntry(name="itemsToInsert", source=source[1]),
                InputFieldMappingEntry(name="offsets", source=source[2]),
            ],
            outputs=[
                OutputFieldMappingEntry(name="mergedText", target_name="merged_content")
            ],
        )

        return merge_skill

    def get_conditional_skill(self, context, source) -> ConditionalSkill:
        """Get the merge
        Args:
        -----
            context (str): The context of the skill
            source (array): The source of the skill

        Returns:
        --------
            ConditionalSkill: The conditional skill"""

        conditional_skill = ConditionalSkill(
            description="Select between OCR and Document Extraction output",
            context=context,
            inputs=[
                InputFieldMappingEntry(name="condition", source=source[0]),
                InputFieldMappingEntry(name="whenTrue", source=source[1]),
                InputFieldMappingEntry(name="whenFalse", source=source[2]),
            ],
            outputs=[
                OutputFieldMappingEntry(name="output", target_name="updated_content")
            ],
        )

        return conditional_skill

    def get_compass_vector_search(self) -> VectorSearch:
        """Get the vector search configuration for compass.

        Args:
            indexer_type (str): The type of the indexer

        Returns:
            VectorSearch: The vector search configuration
        """

        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name=self.algorithm_name),
            ],
            profiles=[
                VectorSearchProfile(
                    name=self.vector_search_profile_name,
                    algorithm_configuration_name=self.algorithm_name,
                    vectorizer=self.vectorizer_name,
                )
            ],
            vectorizers=[
                CustomVectorizer(
                    name=self.vectorizer_name,
                    custom_web_api_parameters=CustomWebApiParameters(
                        uri=get_custom_skill_function_url("compass"),
                        auth_resource_id=get_function_app_authresourceid(),
                        auth_identity=self.get_user_assigned_managed_identity(),
                    ),
                ),
            ],
        )

        return vector_search

    def deploy_index(self):
        """This function deploys index"""

        index_fields = self.get_index_fields()
        vector_search = self.get_compass_vector_search()
        semantic_search = self.get_semantic_search()
        index = SearchIndex(
            name=self.index_name,
            fields=index_fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )
        if self.rebuild:
            self._search_index_client.delete_index(self.index_name)
        self._search_index_client.create_or_update_index(index)

        print(f"{index.name} created")

    def deploy_skillset(self):
        """This function deploys the skillset."""
        skills = self.get_skills()
        index_projections = self.get_index_projections()

        skillset = SearchIndexerSkillset(
            name=self.skillset_name,
            description="Skillset to chunk documents and generating embeddings",
            skills=skills,
            index_projections=index_projections,
        )

        self._search_indexer_client.create_or_update_skillset(skillset)
        print(f"{skillset.name} created")

    def deploy_data_source(self):
        """This function deploys the data source."""
        data_source = self.get_data_source()

        result = self._search_indexer_client.create_or_update_data_source_connection(
            data_source
        )

        print(f"Data source '{result.name}' created or updated")

        return result

    def deploy_indexer(self):
        """This function deploys the indexer."""
        indexer = self.get_indexer()

        result = self._search_indexer_client.create_or_update_indexer(indexer)

        print(f"Indexer '{result.name}' created or updated")

        return result

    def run_indexer(self):
        """This function runs the indexer."""
        self._search_indexer_client.run_indexer(self.indexer_name)

        print(
            f"{self.indexer_name} is running. If queries return no results, please wait a bit and try again."
        )

    def reset_indexer(self):
        """This function runs the indexer."""
        self._search_indexer_client.reset_indexer(self.indexer_name)

        print(f"{self.indexer_name} reset.")

    def deploy_synonym_map(self) -> list[SearchableField]:
        synonym_maps = self.get_synonym_map_names()
        if len(synonym_maps) > 0:
            for synonym_map in synonym_maps:
                try:
                    synonym_map = SynonymMap(name=synonym_map, synonyms="")
                    self._search_index_client.create_synonym_map(synonym_map)
                except HttpResponseError:
                    print("Unable to deploy synonym map as it already exists.")

    def deploy(self):
        """This function deploys the whole AI search pipeline."""
        self.deploy_data_source()
        self.deploy_synonym_map()
        self.deploy_index()
        self.deploy_skillset()
        self.deploy_indexer()

        print(f"{str(self.indexer_type.value)} deployed")
