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

    async def run_completion_request(
        self, messages: list[dict], temperature=0, max_tokens=2000, model="4o-mini"
    ) -> str:
        if model == "4o-mini":
            model_deployment = os.environ["OpenAI__MiniCompletionDeployment"]
        elif model == "4o":
            model_deployment = os.environ["OpenAI__CompletionDeployment"]
        else:
            raise ValueError(f"Model {model} not found")

        token_provider, api_key = self.get_authentication_properties()
        async with AsyncAzureOpenAI(
            azure_deployment=model_deployment,
            api_version=os.environ["OpenAI__ApiVersion"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            azure_ad_token_provider=token_provider,
            api_key=api_key,
        ) as open_ai_client:
            response = await open_ai_client.chat.completions.create(
                model=model_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return response.choices[0].message.content

    async def run_embedding_request(self, batch: list[str]):
        token_provider, api_key = self.get_authentication_properties()

        model_deployment = os.environ["OpenAI__EmbeddingModel"]
        async with AsyncAzureOpenAI(
            azure_deployment=model_deployment,
            api_version=os.environ["OpenAI__ApiVersion"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            azure_ad_token_provider=token_provider,
            api_key=api_key,
        ) as open_ai_client:
            embeddings = await open_ai_client.embeddings.create(
                model=os.environ["OpenAI__EmbeddingModel"],
                input=batch,
            )

        return embeddings
