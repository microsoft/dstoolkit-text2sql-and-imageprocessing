# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
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
    AzureOpenAIEmbeddingSkill,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SearchIndexer,
    SearchIndexerSkillset,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataSourceType,
    OutputFieldMappingEntry,
    InputFieldMappingEntry,
    SynonymMap,
    SplitSkill,
    SearchIndexerIndexProjection,
    BlobIndexerParsingMode,
)
from azure.core.exceptions import HttpResponseError
from azure.search.documents.indexes import SearchIndexerClient, SearchIndexClient
from environment import AISearchEnvironment, IdentityType


class AISearch(ABC):
    """Handles the deployment of the AI search pipeline."""

    def __init__(
        self,
        suffix: str | None = None,
        rebuild: bool | None = False,
    ):
        """Initialize the AI search class

        Args:
            suffix (str, optional): The suffix for the indexer. Defaults to None. If an suffix is provided, it is assumed to be a test indexer.
            rebuild (bool, optional): Whether to rebuild the index. Defaults to False.
        """

        if not hasattr(self, "indexer_type"):
            # Needed to help mypy understand that indexer_type is defined in the child class
            self.indexer_type = None
            raise ValueError("indexer_type is not defined in the child class.")

        if rebuild is not None:
            self.rebuild = rebuild
        else:
            self.rebuild = False

        # If suffix is None, then it is not a test indexer. Test indexer limits the rate of indexing and turns off the schedule. Useful for testing index changes
        if suffix is None:
            self.suffix = ""
            self.test = False
        else:
            self.suffix = f"-{suffix}-test"
            self.test = True

        self.environment = AISearchEnvironment(indexer_type=self.indexer_type)

        self._search_indexer_client = SearchIndexerClient(
            endpoint=self.environment.ai_search_endpoint,
            credential=self.environment.ai_search_credential,
        )
        self._search_index_client = SearchIndexClient(
            endpoint=self.environment.ai_search_endpoint,
            credential=self.environment.ai_search_credential,
        )

        self.parsing_mode = BlobIndexerParsingMode.DEFAULT

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
        blob_container_name = self.environment.storage_account_blob_container_name
        return f"{blob_container_name}-data-source{self.suffix}"

    @property
    def vector_search_profile_name(self):
        """Get the vector search profile name for the indexer."""
        return f"{str(self.indexer_type.value)}-vector-search-profile{self.suffix}"

    @property
    def vectorizer_name(self):
        """Get the vectorizer name."""
        return f"{str(self.indexer_type.value)}-vectorizer{self.suffix}"

    @property
    def algorithm_name(self):
        """Get the algorithm name"""

        return f"{str(self.indexer_type.value)}-algorithm{self.suffix}"

    @abstractmethod
    def get_index_fields(self) -> list[SearchableField]:
        """Get the index fields for the indexer.

        Returns:
            list[SearchableField]: The index fields"""

    def get_semantic_search(self) -> SemanticSearch:
        """Get the semantic search configuration for the indexer.

        Returns:
            SemanticSearch: The semantic search configuration"""

        return None

    def get_skills(self) -> list:
        """Get the skillset for the indexer.

        Returns:
            list: The skillsets  used in the indexer"""

        return []

    def get_indexer(self) -> SearchIndexer:
        """Get the indexer for the indexer."""

        return None

    def get_index_projections(self) -> SearchIndexerIndexProjection:
        """Get the index projections for the indexer."""

        return None

    def get_synonym_map_names(self) -> list[str]:
        """Get the synonym map names for the indexer."""
        return []

    def get_data_source(self) -> SearchIndexerDataSourceConnection:
        """Get the data source for the indexer."""

        if self.get_indexer() is None:
            return None

        if self.parsing_mode in [
            BlobIndexerParsingMode.DEFAULT,
            BlobIndexerParsingMode.TEXT,
            BlobIndexerParsingMode.JSON,
        ]:
            data_deletion_detection_policy = (
                NativeBlobSoftDeleteDeletionDetectionPolicy()
            )
        else:
            data_deletion_detection_policy = None

        data_change_detection_policy = HighWaterMarkChangeDetectionPolicy(
            high_water_mark_column_name="metadata_storage_last_modified"
        )

        container = SearchIndexerDataContainer(
            name=self.environment.storage_account_blob_container_name
        )

        data_source_connection = SearchIndexerDataSourceConnection(
            name=self.data_source_name,
            type=SearchIndexerDataSourceType.AZURE_BLOB,
            connection_string=self.environment.storage_account_connection_string,
            container=container,
            data_change_detection_policy=data_change_detection_policy,
            data_deletion_detection_policy=data_deletion_detection_policy,
        )

        if self.environment.identity_type != IdentityType.KEY:
            data_source_connection.identity = self.environment.ai_search_identity_id

        return data_source_connection

    def get_mark_up_cleaner_skill(self, context, source) -> WebApiSkill:
        """Get the custom skill for data cleanup.

        Args:
        -----
            context (str): The context of the skill
            source (str): The source of the skill

        Returns:
        --------
            WebApiSkill: The custom skill for data cleanup"""

        if self.test:
            batch_size = 2
            degree_of_parallelism = 2
        else:
            batch_size = 16
            degree_of_parallelism = 16

        mark_up_cleaner_skill_inputs = [
            InputFieldMappingEntry(name="chunk", source=source)
        ]

        mark_up_cleaner_skill_outputs = [
            OutputFieldMappingEntry(name="cleaned_chunk", target_name="cleaned_chunk")
        ]

        mark_up_cleaner_skill = WebApiSkill(
            name="Pre Embedding Cleaner Skill",
            description="Skill to clean the data before sending to embedding",
            context=context,
            uri=self.environment.get_custom_skill_function_url("mark_up_cleaner"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=mark_up_cleaner_skill_inputs,
            outputs=mark_up_cleaner_skill_outputs,
        )

        if self.environment.identity_type != IdentityType.KEY:
            mark_up_cleaner_skill.auth_identity = (
                self.environment.function_app_app_registration_resource_id
            )

        if self.environment.identity_type == IdentityType.USER_ASSIGNED:
            mark_up_cleaner_skill.auth_identity = (
                self.environment.ai_search_user_assigned_identity
            )

        return mark_up_cleaner_skill

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

        if self.test:
            batch_size = 2
            degree_of_parallelism = 2
        else:
            batch_size = 16
            degree_of_parallelism = 16

        semantic_text_chunker_skill_inputs = [
            InputFieldMappingEntry(name="content", source=source)
        ]

        semantic_text_chunker_skill_outputs = [
            OutputFieldMappingEntry(name="chunks", target_name="chunks"),
        ]

        semantic_text_chunker_skill = WebApiSkill(
            name="Pre Embedding Cleaner Skill",
            description="Skill to clean the data before sending to embedding",
            context=context,
            uri=self.environment.get_custom_skill_function_url("semantic_text_chunker"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=semantic_text_chunker_skill_inputs,
            outputs=semantic_text_chunker_skill_outputs,
        )

        if self.environment.identity_type != IdentityType.KEY:
            semantic_text_chunker_skill.auth_identity = (
                self.environment.function_app_app_registration_resource_id
            )

        if self.environment.identity_type == IdentityType.USER_ASSIGNED:
            semantic_text_chunker_skill.auth_identity = (
                self.environment.ai_search_user_assigned_identity
            )

        return semantic_text_chunker_skill

    def get_adi_skill(self, chunk_by_page=False) -> WebApiSkill:
        """Get the custom skill for adi.

        Args:
        -----
            chunk_by_page (bool, optional): Whether to chunk by page. Defaults to False.

        Returns:
        --------
            WebApiSkill: The custom skill for adi"""

        if self.test:
            batch_size = 1
            degree_of_parallelism = 4
        else:
            # Depending on your GPT Token limit, you may need to adjust the batch size and degree of parallelism
            batch_size = 1
            degree_of_parallelism = 8

        if chunk_by_page:
            output = [
                OutputFieldMappingEntry(name="extracted_content", target_name="chunks")
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
            uri=self.environment.get_custom_skill_function_url("adi"),
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
        )

        if self.environment.identity_type != IdentityType.KEY:
            adi_skill.auth_identity = (
                self.environment.function_app_app_registration_resource_id
            )

        if self.environment.identity_type == IdentityType.USER_ASSIGNED:
            adi_skill.auth_identity = self.environment.ai_search_user_assigned_identity

        return adi_skill

    def get_vector_skill(
        self, context, source, target_name="vector"
    ) -> AzureOpenAIEmbeddingSkill:
        """Get the vector skill for the indexer.

        Returns:
            AzureOpenAIEmbeddingSkill: The vector skill for the indexer"""

        embedding_skill_inputs = [
            InputFieldMappingEntry(name="text", source=source),
        ]
        embedding_skill_outputs = [
            OutputFieldMappingEntry(name="embedding", target_name=target_name)
        ]

        vector_skill = AzureOpenAIEmbeddingSkill(
            name="Vector Skill",
            description="Skill to generate embeddings",
            context=context,
            deployment_name=self.environment.open_ai_embedding_deployment,
            model_name=self.environment.open_ai_embedding_model,
            resource_url=self.environment.open_ai_endpoint,
            inputs=embedding_skill_inputs,
            outputs=embedding_skill_outputs,
            dimensions=self.environment.open_ai_embedding_dimensions,
        )

        if self.environment.identity_type == IdentityType.KEY:
            vector_skill.api_key = self.environment.open_ai_api_key
        elif self.environment.identity_type == IdentityType.USER_ASSIGNED:
            vector_skill.auth_identity = (
                self.environment.ai_search_user_assigned_identity
            )

        return vector_skill

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

        key_phrase_extraction_skill_inputs = [
            InputFieldMappingEntry(name="text", source=source),
        ]
        key_phrase_extraction__skill_outputs = [
            OutputFieldMappingEntry(name="key_phrases", target_name="keywords")
        ]
        key_phrase_extraction_skill = WebApiSkill(
            name="Key phrase extraction API",
            description="Skill to extract keyphrases",
            context=context,
            uri=self.environment.get_custom_skill_function_url("key_phrase_extraction"),
            timeout="PT230S",
            batch_size=batch_size,
            degree_of_parallelism=degree_of_parallelism,
            http_method="POST",
            inputs=key_phrase_extraction_skill_inputs,
            outputs=key_phrase_extraction__skill_outputs,
        )

        if self.environment.identity_type != IdentityType.KEY:
            key_phrase_extraction_skill.auth_identity = (
                self.environment.function_app_app_registration_resource_id
            )

        if self.environment.identity_type == IdentityType.USER_ASSIGNED:
            key_phrase_extraction_skill.auth_identity = (
                self.environment.ai_search_user_assigned_identity
            )

        return key_phrase_extraction_skill

    def get_vector_search(self) -> VectorSearch:
        """Get the vector search configuration for compass.

        Args:
            indexer_type (str): The type of the indexer

        Returns:
            VectorSearch: The vector search configuration
        """

        open_ai_params = AzureOpenAIVectorizerParameters(
            resource_url=self.environment.open_ai_endpoint,
            model_name=self.environment.open_ai_embedding_model,
            deployment_name=self.environment.open_ai_embedding_deployment,
        )

        if self.environment.identity_type == IdentityType.KEY:
            open_ai_params.api_key = self.environment.open_ai_api_key
        elif self.environment.identity_type == IdentityType.USER_ASSIGNED:
            open_ai_params.auth_identity = (
                self.environment.ai_search_user_assigned_identity
            )

        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name=self.algorithm_name),
            ],
            profiles=[
                VectorSearchProfile(
                    name=self.vector_search_profile_name,
                    algorithm_configuration_name=self.algorithm_name,
                    vectorizer_name=self.vectorizer_name,
                )
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name=self.vectorizer_name,
                    parameters=open_ai_params,
                ),
            ],
        )

        return vector_search

    def deploy_index(self):
        """This function deploys index"""

        index_fields = self.get_index_fields()
        vector_search = self.get_vector_search()
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

        logging.info("%s index created", index.name)

    def deploy_skillset(self):
        """This function deploys the skillset."""
        skills = self.get_skills()

        if len(skills) == 0:
            logging.warning("No skills defined. Skipping skillset deployment.")

            return

        index_projections = self.get_index_projections()

        skillset = SearchIndexerSkillset(
            name=self.skillset_name,
            description="Skillset to chunk documents and generating embeddings",
            skills=skills,
            index_projection=index_projections,
        )

        self._search_indexer_client.create_or_update_skillset(skillset)

        logging.info("%s skillset created", skillset.name)

    def deploy_data_source(self):
        """This function deploys the data source."""
        data_source = self.get_data_source()

        if data_source is None:
            logging.warning("Data source not defined. Skipping data source deployment.")

            return

        result = self._search_indexer_client.create_or_update_data_source_connection(
            data_source
        )

        logging.info("%s data source created", result.name)

    def deploy_indexer(self):
        """This function deploys the indexer."""
        indexer = self.get_indexer()

        if indexer is None:
            logging.warning("Indexer not defined. Skipping data source deployment.")

            return

        result = self._search_indexer_client.create_or_update_indexer(indexer)

        logging.info("%s indexer created", result.name)

    def run_indexer(self):
        """This function runs the indexer."""
        self._search_indexer_client.run_indexer(self.indexer_name)

        logging.info(
            "%s is running. If queries return no results, please wait a bit and try again.",
            self.indexer_name,
        )

    def reset_indexer(self):
        """This function runs the indexer."""

        if self.get_indexer() is None:
            logging.warning("Indexer not defined. Skipping reset operation.")

            return
        self._search_indexer_client.reset_indexer(self.indexer_name)

        logging.info("%s reset.", self.indexer_name)

    def deploy_synonym_map(self):
        """This function deploys the synonym map."""

        synonym_maps = self.get_synonym_map_names()
        if len(synonym_maps) > 0:
            for synonym_map in synonym_maps:
                try:
                    synonym_map = SynonymMap(name=synonym_map, synonyms="")
                    self._search_index_client.create_or_update_synonym_map(synonym_map)
                except HttpResponseError as e:
                    logging.error("Unable to deploy synonym map. %s", e)

    def deploy(self):
        """This function deploys the whole AI search pipeline."""
        self.deploy_data_source()
        self.deploy_synonym_map()
        self.deploy_index()
        self.deploy_skillset()
        self.deploy_indexer()

        logging.info("%s setup deployed", self.indexer_type.value)
