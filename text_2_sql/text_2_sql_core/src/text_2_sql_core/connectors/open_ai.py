# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License
from openai import AsyncAzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import os
import dotenv
from text_2_sql_core.utils.environment import IdentityType, get_identity_type

dotenv.load_dotenv()


class OpenAIConnector:
    @classmethod
    def get_authentication_properties(cls) -> dict:
        if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
            # Create the token provider
            api_key = None
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )
        elif get_identity_type() == IdentityType.USER_ASSIGNED:
            # Create the token provider
            api_key = None
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(
                    managed_identity_client_id=os.environ["ClientId"]
                ),
                "https://cognitiveservices.azure.com/.default",
            )
        else:
            token_provider = None
            api_key = os.environ["OpenAI__ApiKey"]

        return token_provider, api_key

    async def run_completion_request(self, messages: list[dict], temperature=0):
        token_provider, api_key = self.get_authentication_properties()
        async with AsyncAzureOpenAI(
            azure_deployment=os.environ["OpenAI__MiniCompletionDeployment"],
            api_version=os.environ["OpenAI__ApiVersion"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            azure_ad_token_provider=token_provider,
            api_key=api_key,
        ) as open_ai_client:
            response = await open_ai_client.chat.completions.create(
                model=os.environ["OpenAI__MiniCompletionDeployment"],
                messages=messages,
                temperature=temperature,
            )
        return response.choices[0].message.content
