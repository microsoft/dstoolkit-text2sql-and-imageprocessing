from azure.search.documents.indexes.aio import SearchIndexerClient, SearchIndexClient
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.models import SynonymMap
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import HttpResponseError
import logging
import os
from enum import Enum
from openai import AsyncAzureOpenAI
from azure.search.documents.models import VectorizedQuery


class IndexerStatusEnum(Enum):
    RETRIGGER = "RETRIGGER"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"


class AISearchHelper:
    def __init__(self):
        self._client_id = os.environ["FunctionApp__ClientId"]

        self._endpoint = os.environ["AIService__AzureSearchOptions__Endpoint"]

    async def get_index_client(self):
        credential = DefaultAzureCredential(managed_identity_client_id=self._client_id)

        return SearchIndexClient(self._endpoint, credential)

    async def get_indexer_client(self):
        credential = DefaultAzureCredential(managed_identity_client_id=self._client_id)

        return SearchIndexerClient(self._endpoint, credential)

    async def get_search_client(self, index_name):
        credential = DefaultAzureCredential(managed_identity_client_id=self._client_id)

        return SearchClient(self._endpoint, index_name, credential)

    async def upload_synonym_map(self, synonym_map_name: str, synonyms: str):
        index_client = await self.get_index_client()
        async with index_client:
            try:
                await index_client.delete_synonym_map(synonym_map_name)
            except HttpResponseError as e:
                logging.error("Unable to delete synonym map %s", e)

            logging.info("Synonyms: %s", synonyms)
            synonym_map = SynonymMap(name=synonym_map_name, synonyms=synonyms)
            await index_client.create_synonym_map(synonym_map)

    async def get_indexer_status(self, indexer_name):
        indexer_client = await self.get_indexer_client()
        async with indexer_client:
            try:
                status = await indexer_client.get_indexer_status(indexer_name)

                last_execution_result = status.last_result

                if last_execution_result.status == "inProgress":
                    return IndexerStatusEnum.RUNNING, last_execution_result.start_time
                elif last_execution_result.status in ["success", "transientFailure"]:
                    return IndexerStatusEnum.SUCCESS, last_execution_result.start_time
                else:
                    return IndexerStatusEnum.RETRIGGER, last_execution_result.start_time
            except HttpResponseError as e:
                logging.error("Unable to get indexer status %s", e)

    async def trigger_indexer(self, indexer_name):
        indexer_client = await self.get_indexer_client()
        async with indexer_client:
            try:
                await indexer_client.run_indexer(indexer_name)
            except HttpResponseError as e:
                logging.error("Unable to run indexer %s", e)

    async def search_index(
        self, index_name, semantic_config, search_text, deal_id=None
    ):
        """Search the index using the provided search text."""
        async with AsyncAzureOpenAI(
            # This is the default and can be omitted
            api_key=os.environ["AIService__Compass_Key"],
            azure_endpoint=os.environ["AIService__Compass_Endpoint"],
            api_version="2023-03-15-preview",
        ) as open_ai_client:
            embeddings = await open_ai_client.embeddings.create(
                model=os.environ["AIService__Compass_Models__Embedding"],
                input=search_text,
            )

            # Extract the embedding vector
            embedding_vector = embeddings.data[0].embedding

        vector_query = VectorizedQuery(
            vector=embedding_vector,
            k_nearest_neighbors=5,
            fields="ChunkEmbedding",
        )

        if deal_id:
            filter_expression = f"DealId eq '{deal_id}'"
        else:
            filter_expression = None

        logging.info(f"Filter Expression: {filter_expression}")

        search_client = await self.get_search_client(index_name)
        async with search_client:
            results = await search_client.search(
                top=3,
                query_type="semantic",
                semantic_configuration_name=semantic_config,
                search_text=search_text,
                select="Title,Chunk",
                vector_queries=[vector_query],
                filter=filter_expression,
            )

            documents = [
                document
                async for result in results.by_page()
                async for document in result
            ]

            logging.info(f"Documents: {documents}")
        return documents
