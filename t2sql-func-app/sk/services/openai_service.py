# import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv()


class OpenAIService:
    def __init__(self):
        self.endpoint = "https://aoai-text2sql-adi.openai.azure.com/"
        # os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment_name = "gpt-4o"
        # os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        self.client = AzureOpenAI(
            api_version="2024-05-13",
            azure_endpoint=self.endpoint,
            azure_ad_token_provider=token_provider
        )

    def get_response(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message['content']
