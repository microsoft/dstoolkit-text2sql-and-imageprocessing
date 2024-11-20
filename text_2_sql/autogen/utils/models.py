from autogen_ext.models import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import os

# Create the token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

MINI_MODEL = AzureOpenAIChatCompletionClient(
    model="{your-azure-deployment}",
    api_version="2024-06-01",
    azure_endpoint=os.environ["OpenAI__Endpoint"],
    # Optional if you choose key-based authentication.
    azure_ad_token_provider=token_provider,
    # api_key="sk-...", # For key-based authentication.
    model_capabilities={
        "vision": False,
        "function_calling": True,
        "json_output": True,
    },
)
