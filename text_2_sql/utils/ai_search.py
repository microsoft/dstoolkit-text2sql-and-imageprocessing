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
import base64
from datetime import datetime, timezone


async def run_ai_search_query(
    query,
    vector_fields: list[str],
    retrieval_fields: list[str],
    index_name: str,
    semantic_config: str,
    top=5,
    include_scores=False,
    minimum_score: float = None,
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
            top=top,
            semantic_configuration_name=semantic_config,
            search_text=query,
            select=",".join(retrieval_fields),
            vector_queries=[vector_query],
            query_type="semantic",
            query_language="en-GB",
        )

        combined_results = []

        async for result in results.by_page():
            async for item in result:
                if (
                    minimum_score is not None
                    and item["@search.reranker_score"] < minimum_score
                ):
                    continue

                if include_scores is False:
                    del item["@search.reranker_score"]
                    del item["@search.score"]
                    del item["@search.highlights"]
                    del item["@search.captions"]

                logging.info("Item: %s", item)
                combined_results.append(item)

        logging.info("Results: %s", combined_results)

    return combined_results


async def add_entry_to_index(document: dict, vector_fields: dict, index_name: str):
    """Add an entry to the search index."""

    logging.info("Document: %s", document)
    logging.info("Vector Fields: %s", vector_fields)

    for field in vector_fields.keys():
        if field not in document.keys():
            raise ValueError(f"Field {field} is not in the document.")

    identity_type = get_identity_type()

    fields_to_embed = {field: document[field] for field in vector_fields}

    document["DateLastModified"] = datetime.now(timezone.utc)

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
        for i, field in enumerate(vector_fields.values()):
            document[field] = embeddings.data[i].embedding

    document["Id"] = base64.urlsafe_b64encode(document["Question"].encode()).decode(
        "utf-8"
    )
    logging.info("Document with embeddings: %s", document)

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
