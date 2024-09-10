# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from dotenv import find_dotenv, load_dotenv
from enum import Enum
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

class IndexerType(Enum):
    """The type of the indexer"""

    RAG_DOCUMENTS = "rag-documents"

class IdentityType(Enum):
    """The type of the indexer"""

    USER_ASSIGNED = "user_assigned"
    SYSTEM_ASSIGNED = "system_assigned"
    KEY = "key"

class AISearchEnvironment:
    """This class is used to get the environment variables for the AI search service."""
    def __init__(self, indexer_type: IndexerType):
        """Initialize the AISearchEnvironment class.

        Args:
            indexer_type (IndexerType): The type of the indexer
        """
        load_dotenv(find_dotenv())
        self.indexer_type = indexer_type

    @property
    def normalised_indexer_type(self) -> str:
        """This function returns the normalised indexer type.
        
        Returns:
            str: The normalised indexer type
        """
        normalised_indexer_type = (
            self.indexer_type.value.replace("-", " ").title().replace(" ", "")
        )

        return normalised_indexer_type

    @property
    def identity_type(self) -> IdentityType:
        """This function returns the identity type.
        
        Returns:
            IdentityType: The identity type
        """
        identity = os.environ.get("AIService__AzureSearchOptions__IdentityType")

        if identity == "user_assigned":
            return IdentityType.USER_ASSIGNED
        elif identity == "system_assigned":
            return IdentityType.SYSTEM_ASSIGNED
        elif identity == "key":
            return IdentityType.KEY
        else:
            raise ValueError("Invalid identity type")
        
    @property
    def ai_search_endpoint(self) -> str:
        """This function returns the ai search endpoint.
        
        Returns:
            str: The ai search endpoint
        """
        return os.environ.get("AIService__AzureSearchOptions__Endpoint")

    @property
    def ai_search_credential(self) -> DefaultAzureCredential | AzureKeyCredential:
        """This function returns the ai search credential.
        
        Returns:
            DefaultAzureCredential | AzureKeyCredential: The ai search credential
        """
        if self.identity_type in IdentityType.SYSTEM_ASSIGNED:
            return DefaultAzureCredential()
        elif self.identity_type in IdentityType.USER_ASSIGNED:
            return DefaultAzureCredential(managed_identity_client_id =os.environ.get("AIService__AzureSearchOptions__ManagedIdentity__FQName"))
        else:
            return AzureKeyCredential(os.environ.get("AIService__AzureSearchOptions__Key__Secret"))

    @property
    def storage_account_connection_string(self) -> str:
        """This function returns the blob connection string. If the identity type is user_assigned or system_assigned, it returns the FQEndpoint, otherwise it returns the ConnectionString"""
        if self.identity_type in [IdentityType.SYSTEM_ASSIGNED, IdentityType.USER_ASSIGNED]:
            return os.environ.get("StorageAccount__FQEndpoint")
        else:
            return os.environ.get("StorageAccount__ConnectionString")

    @property
    def storage_account_blob_container_name(self) -> str:
        """
        This function returns azure blob container name
        """

        return os.environ.get(f"StorageAccount__{self.normalised_indexer_type}__Container")
    
    @property
    def function_app_end_point(self) -> str:
        """
        This function returns function app endpoint
        """
        return os.environ.get("FunctionApp__Endpoint")

    @property
    def function_app_key(self) -> str:
        """
        This function returns function app key
        """
        return os.environ.get("FunctionApp__Key")
    
    @property
    def function_app_pre_embedding_cleaner_route(self) -> str:
        """
        This function returns function app data cleanup function name
        """
        return os.environ.get("FunctionApp__PreEmbeddingCleaner__FunctionName")

    @property
    def function_app_adi_route(self) -> str:
        """
        This function returns function app adi name
        """
        return os.environ.get("FunctionApp__DocumentIntelligence__FunctionName")

    @property
    def function_app_key_phrase_extractor_route(self) -> str:
        """
        This function returns function app keyphrase extractor name
        """
        return os.environ.get("FunctionApp__KeyphraseExtractor__FunctionName")
    
    def get_custom_skill_function_url(self, skill_type: str):
        """
        Get the function app url that is hosting the custom skill
        """
        if skill_type == "pre_embedding_cleaner":
            route = self.function_app_pre_embedding_cleaner_route
        elif skill_type == "adi":
            route = self.function_app_adi_route
        elif skill_type == "key_phrase_extraction":
            route = self.function_app_key_phrase_extractor_route
        else:
            raise ValueError(f"Invalid skill type: {skill_type}")
        
        full_url = f"{self.function_app_end_point}/api/{route}?code={self.function_app_key}"

        return full_url



# managed identity id
def get_managed_identity_id() -> str:
    """
    This function returns maanged identity id
    """
    return os.environ.get("AIService__AzureSearchOptions__ManagedIdentity__ClientId")


def get_managed_identity_fqname() -> str:
    """
    This function returns maanged identity name
    """
    return os.environ.get("AIService__AzureSearchOptions__ManagedIdentity__FQName")


# function app details
def get_function_app_authresourceid() -> str:
    """
    This function returns apps registration in microsoft entra id
    """
    return os.environ.get("FunctionApp__AuthResourceId")

# search
def get_search_endpoint() -> str:
    """
    This function returns azure ai search service endpoint
    """
    return os.environ.get("AIService__AzureSearchOptions__Endpoint")


def get_search_user_assigned_identity() -> str:
    """
    This function returns azure ai search service endpoint
    """
    return os.environ.get("AIService__AzureSearchOptions__UserAssignedIdentity")


def get_search_key(client) -> str:
    """
    This function returns azure ai search service admin key
    """
    search_service_key_secret_name = (
        str(os.environ.get("AIService__AzureSearchOptions__name")) + "-PrimaryKey"
    )
    retrieved_secret = client.get_secret(search_service_key_secret_name)
    return retrieved_secret.value


def get_search_key_secret() -> str:
    """
    This function returns azure ai search service admin key
    """
    return os.environ.get("AIService__AzureSearchOptions__Key__Secret")


def get_search_embedding_model_dimensions(indexer_type: IndexerType) -> str:
    """
    This function returns dimensions for embedding model
    """

    normalised_indexer_type = (
        indexer_type.value.replace("-", " ").title().replace(" ", "")
    )

    return os.environ.get(
        f"AIService__AzureSearchOptions__{normalised_indexer_type}__EmbeddingDimensions"
    )


def get_blob_container_name(indexer_type: str) -> str:
    """
    This function returns azure blob container name
    """
    normalised_indexer_type = (
        indexer_type.value.replace("-", " ").title().replace(" ", "")
    )
    return os.environ.get(f"StorageAccount__{normalised_indexer_type}__Container")
