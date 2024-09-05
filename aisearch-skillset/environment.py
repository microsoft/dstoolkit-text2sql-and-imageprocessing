"""Module providing environment definition"""
import os
from dotenv import find_dotenv, load_dotenv
from enum import Enum

load_dotenv(find_dotenv())


class IndexerType(Enum):
    """The type of the indexer"""

    INQUIRY_DOCUMENT = "inquiry-document"
    SUMMARY_DOCUMENT = "summary-document"
    BUSINESS_GLOSSARY = "business-glossary"

# key vault
def get_key_vault_url() ->str:
    """
    This function returns key vault url
    """
    return os.environ.get("KeyVault__Url")

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


def get_function_app_end_point() -> str:
    """
    This function returns function app endpoint
    """
    return os.environ.get("FunctionApp__Endpoint")

def get_function_app_key() -> str:
    """
    This function returns function app key
    """
    return os.environ.get("FunctionApp__Key")

def get_function_app_compass_function() -> str:
    """
    This function returns function app compass function name
    """
    return os.environ.get("FunctionApp__Compass__FunctionName")


def get_function_app_pre_embedding_cleaner_function() -> str:
    """
    This function returns function app data cleanup function name
    """
    return os.environ.get("FunctionApp__PreEmbeddingCleaner__FunctionName")


def get_function_app_adi_function() -> str:
    """
    This function returns function app adi name
    """
    return os.environ.get("FunctionApp__DocumentIntelligence__FunctionName")


def get_function_app_custom_split_function() -> str:
    """
    This function returns function app adi name
    """
    return os.environ.get("FunctionApp__CustomTextSplit__FunctionName")


def get_function_app_keyphrase_extractor_function() -> str:
    """
    This function returns function app keyphrase extractor name
    """
    return os.environ.get("FunctionApp__KeyphraseExtractor__FunctionName")


def get_function_app_ocr_function() -> str:
    """
    This function returns function app ocr name
    """
    return os.environ.get("FunctionApp__Ocr__FunctionName")


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
    search_service_key_secret_name = str(os.environ.get("AIService__AzureSearchOptions__name")) + "-PrimaryKey"
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

def get_blob_connection_string() -> str:
    """
    This function returns azure blob storage connection string
    """
    return os.environ.get("StorageAccount__ConnectionString")

def get_fq_blob_connection_string() -> str:
    """
    This function returns azure blob storage connection string
    """
    return os.environ.get("StorageAccount__FQEndpoint")


def get_blob_container_name(indexer_type: str) -> str:
    """
    This function returns azure blob container name
    """
    normalised_indexer_type = (
        indexer_type.value.replace("-", " ").title().replace(" ", "")
    )
    return os.environ.get(f"StorageAccount__{normalised_indexer_type}__Container")


def get_custom_skill_function_url(skill_type: str):
    """
    Get the function app url that is hosting the custom skill
    """
    url = (
        get_function_app_end_point()
        + "/api/function_name?code="
        + get_function_app_key()
    )
    if skill_type == "compass":
        url = url.replace("function_name", get_function_app_compass_function())
    elif skill_type == "pre_embedding_cleaner":
        url = url.replace(
            "function_name", get_function_app_pre_embedding_cleaner_function()
        )
    elif skill_type == "adi":
        url = url.replace("function_name", get_function_app_adi_function())
    elif skill_type == "split":
        url = url.replace("function_name", get_function_app_custom_split_function())
    elif skill_type == "keyphraseextraction":
        url = url.replace(
            "function_name", get_function_app_keyphrase_extractor_function()
        )
    elif skill_type == "ocr":
        url = url.replace("function_name", get_function_app_ocr_function())

    return url
