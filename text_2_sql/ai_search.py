# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from azure.identity import DefaultAzureCredential
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.aio import SearchClient
from environment import IdentityType, get_identity_type
import os
import logging


async def run_ai_search_query(
    query,
    vector_fields: list[str],
    retrieval_fields: list[str],
    index_name: str,
    semantic_config: str,
):
    """Run the AI search query."""
    identity_type = get_identity_type()

    async with AsyncAzureOpenAI(
        # This is the default and can be omitted
        api_key=os.environ["OpenAI__ApiKey"],
        azure_endpoint=os.environ["OpenAI__Endpoint"],
        api_version=os.environ["OpenAI__ApiVersion"],
    ) as open_ai_client:
        embeddings = await open_ai_client.embeddings.create(
            model=os.environ["OpenAI__EmbeddingModel"], input=query
        )

        # Extract the embedding vector
        embedding_vector = embeddings.data[0].embedding

    vector_query = VectorizedQuery(
        vector=embedding_vector,
        k_nearest_neighbors=5,
        fields=",".join(vector_fields),
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
        index_name=index_name,
        credential=credential,
    ) as search_client:
        results = await search_client.search(
            top=5,
            query_type="semantic",
            semantic_configuration_name=semantic_config,
            search_text=query,
            select=",".join(retrieval_fields),
            vector_queries=[vector_query],
        )

        combined_results = [
            result async for results in results.by_page() async for result in results
        ]

    return combined_results


async def add_entry_to_index(document: dict, vector_fields: list[str], index_name: str):
    """Add an entry to the search index."""

    for field in vector_fields:
        if field not in document:
            raise ValueError(f"Field {field} is not in the document.")

    identity_type = get_identity_type()

    fields_to_embed = {field: document[field] for field in vector_fields}

    async with AsyncAzureOpenAI(
        # This is the default and can be omitted
        api_key=os.environ["OpenAI__ApiKey"],
        azure_endpoint=os.environ["OpenAI__Endpoint"],
        api_version=os.environ["OpenAI__ApiVersion"],
    ) as open_ai_client:
        embeddings = await open_ai_client.embeddings.create(
            model=os.environ["OpenAI__EmbeddingModel"], input=fields_to_embed.values()
        )

        # Extract the embedding vector
        for i, field in enumerate(vector_fields):
            document[field] = embeddings.data[i].embedding

    logging.debug("Document with embeddings: %s", document)

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
        index_name=index_name,
        credential=credential,
    ) as search_client:
        await search_client.upload_documents(documents=[document])
