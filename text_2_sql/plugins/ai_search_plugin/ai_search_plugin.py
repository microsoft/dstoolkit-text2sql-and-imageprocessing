# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from semantic_kernel.functions import kernel_function
from typing import Annotated
from azure.identity import DefaultAzureCredential
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.aio import SearchClient
import os
import json
import logging
from enum import Enum


class IdentityType(Enum):
    """The type of the indexer"""

    USER_ASSIGNED = "user_assigned"
    SYSTEM_ASSIGNED = "system_assigned"
    KEY = "key"


class AISearchPlugin:
    """A plugin that allows for the execution of AI Search queries against a text input."""

    @staticmethod
    def system_prompt() -> str:
        """Get the system prompt for the AI Search Plugin."""
        return """Use the AI Search to return documents that have been indexed, that might be relevant for a piece of text to aid understanding. AI Search should always be used, even if you believe it might not be relevant. Execute this in parallel to any other functions that might be relevant."""

    @kernel_function(
        description="Runs an hybrid semantic search against some text to return relevant documents that are indexed within AI Search.",
        name="QueryDocumentStorage",
    )
    async def query_document_storage(
        self, text: Annotated[str, "The text to run a semantic search against."]
    ) -> str:
        """Sends an text query to AI Search and uses Semantic Ranking to return a result.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
        ----
            str: The JSON representation of the search results.
        """

        identity = os.environ.get("IdentityType").lower()

        if identity == "user_assigned":
            identity_type = IdentityType.USER_ASSIGNED
        elif identity == "system_assigned":
            identity_type = IdentityType.SYSTEM_ASSIGNED
        elif identity == "key":
            identity_type = IdentityType.KEY
        else:
            raise ValueError("Invalid identity type")

        async with AsyncAzureOpenAI(
            # This is the default and can be omitted
            api_key=os.environ["OpenAI__ApiKey"],
            azure_endpoint=os.environ["OpenAI__Endpoint"],
            api_version=os.environ["OpenAI__ApiVersion"],
        ) as open_ai_client:
            embeddings = await open_ai_client.embeddings.create(
                model=os.environ["OpenAI__EmbeddingModel"], input=text
            )

            # Extract the embedding vector
            embedding_vector = embeddings.data[0].embedding

        vector_query = VectorizedQuery(
            vector=embedding_vector,
            k_nearest_neighbors=5,
            fields="ChunkEmbedding",
        )

        if identity_type == IdentityType.SYSTEM_ASSIGNED:
            credential = DefaultAzureCredential()
        elif identity_type == IdentityType.USER_ASSIGNED:
            credential = DefaultAzureCredential(
                managed_identity_client_id=os.environ["ClientID"]
            )
        else:
            credential = AzureKeyCredential(
                os.environ["AIService__AzureSearchOptions__Key"]
            )
        async with SearchClient(
            endpoint=os.environ["AIService__AzureSearchOptions__Endpoint"],
            index_name=os.environ["AIService__AzureSearchOptions__RagDocuments__Index"],
            credential=credential,
        ) as search_client:
            results = await search_client.search(
                top=5,
                query_type="semantic",
                semantic_configuration_name=os.environ[
                    "AIService__AzureSearchOptions__RagDocuments__SemanticConfig"
                ],
                search_text=text,
                select="Title,Chunk,SourceUri",
                vector_queries=[vector_query],
            )

            documents = [
                document
                async for result in results.by_page()
                async for document in result
            ]

        logging.debug("Results: %s", documents)
        return json.dumps(documents, default=str)
