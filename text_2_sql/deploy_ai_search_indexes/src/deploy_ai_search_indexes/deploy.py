# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.identity import DefaultAzureCredential
import os
import logging

from text_2_sql_core.utils.environment import IdentityType, get_identity_type
from deploy_ai_search_indexes.text_2_sql_schema_store import create_text_2_sql_schema_store_index
from deploy_ai_search_indexes.text_2_sql_query_cache import create_text_2_sql_query_cache_index
from deploy_ai_search_indexes.text_2_sql_column_value_store import create_text_2_sql_column_value_store_index
from deploy_ai_search_indexes.text_2_sql_schema_cache import create_text_2_sql_schema_cache_index

async def deploy_indexes():
    """Deploy the search indexes."""
    identity_type = get_identity_type()

    if identity_type in [IdentityType.SYSTEM_ASSIGNED, IdentityType.USER_ASSIGNED]:
        credential = DefaultAzureCredential()
    else:
        credential = AzureKeyCredential(os.environ["AIService__AzureSearchOptions__Key"])

    index_client = SearchIndexClient(
        endpoint=os.environ["AIService__AzureSearchOptions__Endpoint"],
        credential=credential,
    )

    # Create schema store index
    schema_store_index = create_text_2_sql_schema_store_index(
        os.environ["AIService__AzureSearchOptions__Text2SqlSchemaStore__Index"]
    )
    index_client.create_or_update_index(schema_store_index)
    logging.info("Created schema store index")

    # Create query cache index
    query_cache_index = create_text_2_sql_query_cache_index(
        os.environ["AIService__AzureSearchOptions__Text2SqlQueryCache__Index"]
    )
    index_client.create_or_update_index(query_cache_index)
    logging.info("Created query cache index")

    # Create column value store index
    column_value_store_index = create_text_2_sql_column_value_store_index(
        os.environ["AIService__AzureSearchOptions__Text2SqlColumnValueStore__Index"]
    )
    index_client.create_or_update_index(column_value_store_index)
    logging.info("Created column value store index")

    # Create schema cache index
    schema_cache_index = create_text_2_sql_schema_cache_index(
        os.environ["AIService__AzureSearchOptions__Text2SqlSchemaCache__Index"]
    )
    index_client.create_or_update_index(schema_cache_index)
    logging.info("Created schema cache index")
