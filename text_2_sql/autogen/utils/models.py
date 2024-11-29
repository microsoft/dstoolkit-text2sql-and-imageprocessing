# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_ext.models import AzureOpenAIChatCompletionClient

# from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import os
import dotenv

dotenv.load_dotenv()

# # Create the token provider
# token_provider = get_bearer_token_provider(
#     DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
# )

GPT_4O_MINI_MODEL = AzureOpenAIChatCompletionClient(
    azure_deployment=os.environ["OpenAI__MiniCompletionDeployment"],
    model=os.environ["OpenAI__MiniCompletionDeployment"],
    api_version="2024-08-01-preview",
    azure_endpoint=os.environ["OpenAI__Endpoint"],
    # # Optional if you choose key-based authentication.
    # azure_ad_token_provider=token_provider,
    api_key=os.environ["OpenAI__ApiKey"],  # For key-based authentication.
    model_capabilities={
        "vision": False,
        "function_calling": True,
        "json_output": True,
    },
)

GPT_4O_MODEL = AzureOpenAIChatCompletionClient(
    azure_deployment=os.environ["OpenAI__CompletionDeployment"],
    model=os.environ["OpenAI__CompletionDeployment"],
    api_version="2024-08-01-preview",
    azure_endpoint=os.environ["OpenAI__Endpoint"],
    # # Optional if you choose key-based authentication.
    # azure_ad_token_provider=token_provider,
    api_key=os.environ["OpenAI__ApiKey"],  # For key-based authentication.
    model_capabilities={
        "vision": False,
        "function_calling": True,
        "json_output": True,
    },
)
