# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from azure.identity import DefaultAzureCredential
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.aio import SearchClient
from text_2_sql_core.utils.environment import IdentityType, get_identity_type
import os
import logging
import base64
from datetime import datetime, timezone
import json
from typing import Annotated


class AISearchConnector:
    async def run_ai_search_query(
        self,
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

        if len(vector_fields) > 0:
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

            vector_query = [
                VectorizedQuery(
                    vector=embedding_vector,
                    k_nearest_neighbors=7,
                    fields=",".join(vector_fields),
                )
            ]
        else:
            vector_query = None

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
            if semantic_config is not None and vector_query is not None:
                query_type = "semantic"
            elif vector_query is not None:
                query_type = "hybrid"
            else:
                query_type = "full"

            results = await search_client.search(
                top=top,
                semantic_configuration_name=semantic_config,
                search_text=query,
                select=",".join(retrieval_fields),
                vector_queries=vector_query,
                query_type=query_type,
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

    async def get_column_values(
        self,
        text: Annotated[
            str,
            "The text to run a semantic search against. Relevant entities will be returned.",
        ],
        as_json: bool = True,
    ):
        """Gets the values of a column in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
        -------
            str: The values of the column in JSON format.
        """

        # Adds tildes after each text word to do a fuzzy search
        text = " ".join([f"{word}~" for word in text.split()])
        values = await self.run_ai_search_query(
            text,
            [],
            ["FQN", "Column", "Value"],
            os.environ[
                "AIService__AzureSearchOptions__Text2SqlColumnValueStore__Index"
            ],
            None,
            top=10,
        )

        if as_json:
            return json.dumps(values, default=str)
        else:
            return values

    async def get_entity_schemas(
        self,
        text: Annotated[
            str,
            "The text to run a semantic search against. Relevant entities will be returned.",
        ],
        excluded_entities: Annotated[
            list[str],
            "The entities to exclude from the search results. Pass the entity property of entities (e.g. 'SalesLT.Address') you already have the schemas for to avoid getting repeated entities.",
        ] = [],
        as_json: bool = True,
    ) -> str:
        """Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
            str: The schema of the views or tables in JSON format.
        """

        schemas = await self.run_ai_search_query(
            text,
            ["DefinitionEmbedding"],
            [
                "FQN",
                "Entity",
                "EntityName",
                "Definition",
                "Columns",
                "EntityRelationships",
                "CompleteEntityRelationshipsGraph",
            ],
            os.environ["AIService__AzureSearchOptions__Text2SqlSchemaStore__Index"],
            os.environ[
                "AIService__AzureSearchOptions__Text2SqlSchemaStore__SemanticConfig"
            ],
            top=3,
        )

        for schema in schemas:
            entity = schema["Entity"]

            filtered_schemas = []
            for excluded_entity in excluded_entities:
                if excluded_entity.lower() == entity.lower():
                    logging.info("Excluded entity: %s", excluded_entity)
                else:
                    filtered_schemas.append(schema)

        if as_json:
            return json.dumps(schemas, default=str)
        else:
            return schemas

    async def add_entry_to_index(document: dict, vector_fields: dict, index_name: str):
        """Add an entry to the search index."""

        logging.info("Document: %s", document)
        logging.info("Vector Fields: %s", vector_fields)

        for field in vector_fields.keys():
            if field not in document.keys():
                logging.error(f"Field {field} is not in the document.")

        identity_type = get_identity_type()

        fields_to_embed = {field: document[field] for field in vector_fields}

        document["DateLastModified"] = datetime.now(timezone.utc)

        try:
            async with AsyncAzureOpenAI(
                # This is the default and can be omitted
                api_key=os.environ["OpenAI__ApiKey"],
                azure_endpoint=os.environ["OpenAI__Endpoint"],
                api_version=os.environ["OpenAI__ApiVersion"],
            ) as open_ai_client:
                embeddings = await open_ai_client.embeddings.create(
                    model=os.environ["OpenAI__EmbeddingModel"],
                    input=fields_to_embed.values(),
                )

                # Extract the embedding vector
                for i, field in enumerate(vector_fields.values()):
                    document[field] = embeddings.data[i].embedding

            document["Id"] = base64.urlsafe_b64encode(
                document["Question"].encode()
            ).decode("utf-8")

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
        except Exception as e:
            logging.error("Failed to add item to index.")
            logging.error("Error: %s", e)
