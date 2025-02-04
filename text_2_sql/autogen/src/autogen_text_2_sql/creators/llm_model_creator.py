# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from text_2_sql_core.utils.environment import IdentityType, get_identity_type

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import os
import dotenv

dotenv.load_dotenv()


class LLMModelCreator:
    @classmethod
    def get_model(
        cls, model_name: str, structured_output=None
    ) -> AzureOpenAIChatCompletionClient:
        """Retrieves the model based on the model name.

        Args:
        ----
            model_name (str): The name of the model to retrieve.

        Returns:
            AzureOpenAIChatCompletionClient: The model client."""
        if model_name == "4o-mini":
            return cls.gpt_4o_mini_model(structured_output=structured_output)
        elif model_name == "4o":
            return cls.gpt_4o_model(structured_output=structured_output)
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
    def gpt_4o_mini_model(
        cls, structured_output=None
    ) -> AzureOpenAIChatCompletionClient:
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
            response_format=structured_output,
        )

    @classmethod
    def gpt_4o_model(cls, structured_output=None) -> AzureOpenAIChatCompletionClient:
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
            response_format=structured_output,
        )
