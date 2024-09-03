from semantic_kernel.functions import kernel_function
from typing import Annotated
from azure.identity import DefaultAzureCredential
from openai import AsyncAzureOpenAI
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.aio import SearchClient
import os
import json
import logging


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

        async with AsyncAzureOpenAI(
            # This is the default and can be omitted
            api_key=os.environ["OPEN_AI_KEY"],
            azure_endpoint=os.environ["OPEN_AI_ENDPOINT"],
            api_version=os.environ["OPEN_AI_VERSION"],
        ) as open_ai_client:
            embeddings = await open_ai_client.embeddings.create(
                model=os.environ["OPEN_AI_EMBEDDING_MODEL"], input=text
            )

            # Extract the embedding vector
            embedding_vector = embeddings.data[0].embedding

        vector_query = VectorizedQuery(
            vector=embedding_vector,
            k_nearest_neighbors=5,
            fields="chunk_vector",
        )

        credential = DefaultAzureCredential()
        async with SearchClient(
            endpoint=os.environ["AI_SEARCH_ENDPOINT"],
            index_name=os.environ["AI_SEARCH_INDEX"],
            credential=credential,
        ) as search_client:
            results = await search_client.search(
                top=5,
                query_type="semantic",
                semantic_configuration_name=os.environ["AI_SEARCH_SEMANTIC_CONFIG"],
                search_text=text,
                select="title,chunk,source",
                vector_queries=[vector_query],
            )

            documents = [
                document
                async for result in results.by_page()
                async for document in result
            ]

        logging.debug("Results: %s", documents)
        return json.dumps(documents, default=str)
