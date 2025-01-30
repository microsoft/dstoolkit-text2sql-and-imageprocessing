# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from text_2_sql_core.utils.environment import IdentityType, get_identity_type

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import os
import dotenv
import logging

dotenv.load_dotenv()


class LLMModelCreator:
    @classmethod
    def get_model(cls, model_name: str) -> AzureOpenAIChatCompletionClient:
        """Retrieves the model based on the model name.

        Args:
        ----
            model_name (str): The name of the model to retrieve.

        Returns:
            AzureOpenAIChatCompletionClient: The model client."""
        logging.info(f"Getting model for name: {model_name}")
        if model_name == "4o-mini":
            logging.info(
                "Using GPT-4 Mini model with deployment: %s",
                os.environ["OpenAI__MiniCompletionDeployment"],
            )
            return cls.gpt_4o_mini_model()
        elif model_name == "4o":
            logging.info(
                "Using full GPT-4 model with deployment: %s",
                os.environ["OpenAI__CompletionDeployment"],
            )
            return cls.gpt_4o_model()
        else:
            raise ValueError(f"Model {model_name} not found")

    @classmethod
    def get_authentication_properties(cls) -> dict:
        if get_identity_type() in [
            IdentityType.SYSTEM_ASSIGNED,
            IdentityType.USER_ASSIGNED,
        ]:
            # Create the token provider
            api_key = None
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )
        else:
            token_provider = None
            api_key = os.environ["OpenAI__ApiKey"]

        return token_provider, api_key

    @classmethod
    def gpt_4o_mini_model(cls) -> AzureOpenAIChatCompletionClient:
        token_provider, api_key = cls.get_authentication_properties()
        return AzureOpenAIChatCompletionClient(
            azure_deployment=os.environ["OpenAI__MiniCompletionDeployment"],
            model=os.environ["OpenAI__MiniCompletionDeployment"],
            api_version=os.environ["OpenAI__ApiVersion"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            azure_ad_token_provider=token_provider,
            api_key=api_key,
            model_capabilities={
                "vision": False,
                "function_calling": True,
                "json_output": True,
            },
            temperature=0,
        )

    @classmethod
    def gpt_4o_model(cls) -> AzureOpenAIChatCompletionClient:
        token_provider, api_key = cls.get_authentication_properties()
        return AzureOpenAIChatCompletionClient(
            azure_deployment=os.environ["OpenAI__CompletionDeployment"],
            model=os.environ["OpenAI__CompletionDeployment"],
            api_version=os.environ["OpenAI__ApiVersion"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            azure_ad_token_provider=token_provider,
            api_key=api_key,
            model_capabilities={
                "vision": False,
                "function_calling": True,
                "json_output": True,
            },
            temperature=0,
        )
