# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from dotenv import find_dotenv, load_dotenv
from enum import Enum
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes.models import SearchIndexerDataUserAssignedIdentity


class IndexerType(Enum):
    """The type of the indexer"""

    IMAGE_PROCESSING = "image-processing"
    TEXT_2_SQL_SCHEMA_STORE = "text-2-sql-schema-store"
    TEXT_2_SQL_QUERY_CACHE = "text-2-sql-query-cache"
    TEXT_2_SQL_COLUMN_VALUE_STORE = "text-2-sql-column-value-store"


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
        identity = os.environ.get("IdentityType").lower()

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
    def ai_search_identity_id(self) -> str:
        """This function returns the ai search identity id.

        Returns:
            str: The ai search identity id
        """
        return os.environ.get("AIService__AzureSearchOptions__Identity__ClientId")

    @property
    def ai_search_user_assigned_identity(self) -> SearchIndexerDataUserAssignedIdentity:
        """This function returns the ai search user assigned identity.

        Returns:
            SearchIndexerDataUserAssignedIdentity: The ai search user assigned identity
        """
        user_assigned_identity = SearchIndexerDataUserAssignedIdentity(
            resource_id=os.environ.get(
                "AIService__AzureSearchOptions__Identity__FQName"
            )
        )
        return user_assigned_identity

    @property
    def ai_search_credential(self) -> DefaultAzureCredential | AzureKeyCredential:
        """This function returns the ai search credential.

        Returns:
            DefaultAzureCredential | AzureKeyCredential: The ai search credential
        """
        if self.identity_type in [
            IdentityType.SYSTEM_ASSIGNED,
            IdentityType.USER_ASSIGNED,
        ]:
            return DefaultAzureCredential()
        else:
            return AzureKeyCredential(
                os.environ.get("AIService__AzureSearchOptions__Key")
            )

    @property
    def open_ai_api_key(self) -> str:
        """This function returns the open ai api key.

        Returns:
            str: The open ai api key
        """
        return os.environ.get("OpenAI__ApiKey")

    @property
    def open_ai_endpoint(self) -> str:
        """This function returns the open ai endpoint.

        Returns:
            str: The open ai endpoint
        """
        return os.environ.get("OpenAI__Endpoint")

    @property
    def open_ai_embedding_model(self) -> str:
        """This function returns the open ai embedding model.

        Returns:
            str: The open ai embedding model
        """
        return os.environ.get("OpenAI__EmbeddingModel")

    @property
    def open_ai_embedding_deployment(self) -> str:
        """This function returns the open ai embedding deployment.

        Returns:
            str: The open ai embedding deployment
        """
        return os.environ.get("OpenAI__EmbeddingDeployment")

    @property
    def storage_account_connection_string(self) -> str:
        """This function returns the blob connection string. If the identity type is user_assigned or system_assigned, it returns the FQEndpoint, otherwise it returns the ConnectionString"""
        if self.identity_type in [
            IdentityType.SYSTEM_ASSIGNED,
            IdentityType.USER_ASSIGNED,
        ]:
            return os.environ.get("StorageAccount__FQEndpoint")
        else:
            return os.environ.get("StorageAccount__ConnectionString")

    @property
    def storage_account_blob_container_name(self) -> str:
        """
        This function returns azure blob container name
        """

        container = os.environ.get(
            f"StorageAccount__{self.normalised_indexer_type}__Container"
        )

        if container is None:
            raise ValueError(
                f"""Populate environment variable 'StorageAccount__{
                    self.normalised_indexer_type}__Container' with container name."""
            )

        return container

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
    def function_app_app_registration_resource_id(self) -> str:
        """
        This function returns function app app registration resource id
        """
        return os.environ.get("FunctionApp__AppRegistrationResourceId")

    @property
    def open_ai_embedding_dimensions(self) -> str:
        """
        This function returns dimensions for embedding model.

        Returns:
            str: The dimensions for embedding model
        """

        return os.environ.get("OpenAI__EmbeddingDimensions")

    @property
    def use_private_endpoint(self) -> bool:
        """
        This function returns true if private endpoint is used
        """
        return (
            os.environ.get("AIService__AzureSearchOptions__UsePrivateEndpoint").lower()
            == "true"
        )

    def get_custom_skill_function_url(self, skill_type: str):
        """
        Get the function app url that is hosting the custom skill
        """

        full_url = f"{self.function_app_end_point}/api/{skill_type}?code={self.function_app_key}"

        return full_url
