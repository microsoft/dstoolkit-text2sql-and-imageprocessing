# AI Search Indexing Pre-built Index Setup

The associated scripts in this portion of the repository contains pre-built scripts to deploy the skillset with Azure Document Intelligence.

## Steps for Rag Documents Index Deployment (For Unstructured RAG)

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication.
2. Adjust `rag_documents.py` with any changes to the index / indexer. The `get_skills()` method implements the skills pipeline. Make any adjustments here in the skills needed to enrich the data source.
3. Run `deploy.py` with the following args:

    - `index_type rag`. This selects the `RagDocumentsAISearch` sub class.
    - `enable_page_chunking True`. This determines whether page wise chunking is applied in ADI, or whether the inbuilt skill is used for TextSplit. **Page wise analysis in ADI is recommended to avoid splitting tables / figures across multiple chunks, when the chunking is performed.**
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.

## Steps for Text2SQL Index Deployment (For Structured RAG)

### Schema Store Index

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication.
2. Adjust `text_2_sql_schema_store.py` with any changes to the index / indexer. The `get_skills()` method implements the skills pipeline. Make any adjustments here in the skills needed to enrich the data source.
3. Run `deploy.py` with the following args:

    - `index_type text_2_sql_schema_store`. This selects the `Text2SQLSchemaStoreAISearch` sub class.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.
    - `single_data_dictionary_file`. Optional parameter that controls whether you will be uploading a single data dictionary, or a data dictionary file per entity. By default, this is set to False.

### Column Value Store Index

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication.
2. Adjust `text_2_sql_column_value_store.py` with any changes to the index / indexer.
3. Run `deploy.py` with the following args:

    - `index_type text_2_sql_column_value_store`. This selects the `Text2SQLColumnValueStoreAISearch` sub class.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.

### Query Cache Index

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication.
2. Adjust `text_2_sql_query_cache.py` with any changes to the index. **There is an optional provided indexer or skillset for this cache. You may instead want the application code will write directly to it. See the details in the Text2SQL README for different cache strategies.**
3. Run `deploy.py` with the following args:

    - `index_type text_2_sql_query_cache`. This selects the `Text2SQLQueryCacheAISearch` sub class.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.
    - `enable_cache_indexer`. Optional parameter that will enable the query cache indexer. Defaults to False.
    - `single_cache__file`. Optional parameter that controls whether you will be uploading a single data dictionary, or a data dictionary file per entity. By default, this is set to False.

## ai_search.py & environment.py

This includes a variety of helper files and scripts to deploy the index setup. This is useful for CI/CD to avoid having to write JSON files manually or use the UI to deploy the pipeline.
