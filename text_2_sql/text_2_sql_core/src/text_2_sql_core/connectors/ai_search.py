# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import QueryType, VectorizableTextQuery
from azure.search.documents.aio import SearchClient
from text_2_sql_core.utils.environment import IdentityType, get_identity_type
import os
import logging
import base64
from datetime import datetime, timezone
from typing import Annotated
from text_2_sql_core.connectors.open_ai import OpenAIConnector

from text_2_sql_core.utils.database import DatabaseEngineSpecificFields


class AISearchConnector:
    def __init__(self):
        self.open_ai_connector = OpenAIConnector()

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
            vector_query = [
                VectorizableTextQuery(
                    text=query,
                    k_nearest_neighbors=7,
                    fields=",".join(vector_fields),
                )
            ]
        else:
            vector_query = None

        if identity_type in [IdentityType.SYSTEM_ASSIGNED, IdentityType.USER_ASSIGNED]:
            credential = DefaultAzureCredential()
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
                query_type = QueryType.SEMANTIC
            else:
                query_type = QueryType.FULL

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
                        "@search.reranker_score" in item
                        and item["@search.reranker_score"] is not None
                    ):
                        score = item["@search.reranker_score"]
                    elif "@search.score" in item and item["@search.score"] is not None:
                        score = item["@search.score"]
                    else:
                        raise Exception("No score found in the search results.")

                    if minimum_score is not None and score < minimum_score:
                        continue

                    if include_scores is False:
                        if "@search.reranker_score" in item:
                            del item["@search.reranker_score"]
                        if "@search.score" in item:
                            del item["@search.score"]
                        if "@search.highlights" in item:
                            del item["@search.highlights"]
                        if "@search.captions" in item:
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
            vector_fields=[],
            retrieval_fields=["FQN", "Column", "Value"],
            index_name=os.environ[
                "AIService__AzureSearchOptions__Text2SqlColumnValueStore__Index"
            ],
            semantic_config=None,
            top=50,
            include_scores=False,
            minimum_score=5,
        )

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
        engine_specific_fields: Annotated[
            list[DatabaseEngineSpecificFields],
            "The fields specific to the engine to be included in the search results.",
        ] = [],
    ) -> str:
        """Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
            str: The schema of the views or tables in JSON format.
        """

        logging.info("Search Text: %s", text)

        stringified_engine_specific_fields = list(map(str, engine_specific_fields))

        retrieval_fields = [
            "FQN",
            "Entity",
            "EntityName",
            "Schema",
            "Definition",
            "Columns",
            "EntityRelationships",
            "CompleteEntityRelationshipsGraph",
        ] + stringified_engine_specific_fields

        schemas = await self.run_ai_search_query(
            text,
            ["DefinitionEmbedding"],
            retrieval_fields,
            os.environ["AIService__AzureSearchOptions__Text2SqlSchemaStore__Index"],
            os.environ[
                "AIService__AzureSearchOptions__Text2SqlSchemaStore__SemanticConfig"
            ],
            top=3,
            minimum_score=1.5,
        )

        fqn_to_trim = ".".join(stringified_engine_specific_fields)

        if len(excluded_entities) == 0:
            return schemas

        for schema in schemas:
            filtered_schemas = []

            del schema["FQN"]

            if (
                schema["CompleteEntityRelationshipsGraph"] is not None
                and len(schema["CompleteEntityRelationshipsGraph"]) == 0
            ):
                del schema["CompleteEntityRelationshipsGraph"]
            else:
                schema["CompleteEntityRelationshipsGraph"] = list(
                    map(
                        lambda x: x.replace(fqn_to_trim, ""),
                        schema["CompleteEntityRelationshipsGraph"],
                    )
                )

            if schema["SampleValues"] is not None and len(schema["SampleValues"]) == 0:
                del schema["SampleValues"]

            if (
                schema["EntityRelationships"] is not None
                and len(schema["EntityRelationships"]) == 0
            ):
                del schema["EntityRelationships"]

            if schema["Entity"].lower() not in excluded_entities:
                filtered_schemas.append(schema)
            else:
                logging.info("Excluded entity: %s", schema["Entity"])

        logging.info("Filtered Schemas: %s", filtered_schemas)
        return filtered_schemas

    async def add_entry_to_index(
        self, document: dict, vector_fields: dict, index_name: str
    ):
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
            embeddings = await self.open_ai_connector.run_embedding_request(
                list(fields_to_embed.values())
            )

            # Extract the embedding vector
            for i, field in enumerate(vector_fields.values()):
                document[field] = embeddings.data[i].embedding

            document["Id"] = base64.urlsafe_b64encode(
                document["Question"].encode()
            ).decode("utf-8")

            if identity_type in [
                IdentityType.SYSTEM_ASSIGNED,
                IdentityType.USER_ASSIGNED,
            ]:
                credential = DefaultAzureCredential()
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
