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
        self,
        messages: list[dict],
        temperature=0,
        max_tokens=2000,
        model=None,
        response_format=None,
    ) -> str:
        # Use the environment variable for the model, defaulting to 4o
        model = model or os.environ.get("OpenAI__GroupChatModel", "4o")
        model_deployment = os.environ.get("OpenAI__CompletionDeployment") if model == "4o" else os.environ.get("OpenAI__MiniCompletionDeployment")

        # For structured outputs, add a system message requesting JSON format
        if response_format is not None:
            # If response_format is a Pydantic model, get its JSON schema
            if hasattr(response_format, "model_json_schema"):
                schema = response_format.model_json_schema()
            else:
                schema = str(response_format)
            
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You must respond with valid JSON that matches the following schema:\n"
                        f"{schema}\n\n"
                        "Important: Your response must be a valid JSON object that matches this schema exactly."
                    ),
                },
            ] + messages

        token_provider, api_key = self.get_authentication_properties()
        async with AsyncAzureOpenAI(
            azure_deployment=model_deployment,
            api_version=os.environ["OpenAI__ApiVersion"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            azure_ad_token_provider=token_provider,
            api_key=api_key,
        ) as open_ai_client:
            # Always use create() but with response_format={"type": "json_object"} for structured outputs
            response = await open_ai_client.chat.completions.create(
                model=model_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if response_format is not None else None,
            )

        message = response.choices[0].message
        content = message.content

        # If response_format was provided, parse the JSON response
        if response_format is not None:
            import json
            try:
                json_data = json.loads(content)
                # If response_format is a Pydantic model, validate and return an instance
                if hasattr(response_format, "model_validate"):
                    return response_format.model_validate(json_data)
                return json_data
            except json.JSONDecodeError:
                return {"error": "Failed to parse JSON response"}
            except Exception as e:
                return {"error": f"Failed to validate response: {str(e)}"}
        
        return content

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
