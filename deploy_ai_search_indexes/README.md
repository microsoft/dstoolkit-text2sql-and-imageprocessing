# AI Search Indexing Pre-built Index Setup

The associated scripts in this portion of the repository contains pre-built scripts to deploy the skillsets needed for both Text2SQL and Image Processing.

## Steps for Image Processing Index Deployment (For Image Processing)

**Execute the following commands in the `deploy_ai_search_indexes` directory:**

1. Create your `.env` file based on the provided sample `deploy_ai_search_indexes/.env.example`. Place this file in the same place in `deploy_ai_search_indexes/.env`.
2. Run `uv sync` within the `deploy_ai_search_indexes` directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.

**Execute the following commands in the `deploy_ai_search_indexes/src/deploy_ai_search_indexes` directory:**

3. Adjust `image_processing.py` with any changes to the index / indexer. The `get_skills()` method implements the skills pipeline. Make any adjustments here in the skills needed to enrich the data source.
4. Run `uv run deploy.py` with the following args:
    - `index_type image_processing`. This selects the `ImageProcessingAISearch` sub class.
    - `enable_page_wise_chunking True`. This determines whether page wise chunking is applied in ADI, or whether the inbuilt skill is used for TextSplit. This suits documents that are inheritely page-wise e.g. pptx files.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.

## Steps for Text2SQL Index Deployment (For Text2SQL)

### Schema Store Index

**Execute the following commands in the `deploy_ai_search_indexes` directory:**

1. Create your `.env` file based on the provided sample `deploy_ai_search_indexes/.env.example`. Place this file in the same place in `deploy_ai_search_indexes/.env`.
2. Run `uv sync` within the `deploy_ai_search_indexes` directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.

**Execute the following commands in the `deploy_ai_search_indexes/src/deploy_ai_search_indexes` directory:**

3. Adjust `text_2_sql_schema_store.py` with any changes to the index / indexer. The `get_skills()` method implements the skills pipeline. Make any adjustments here in the skills needed to enrich the data source.
4. Run `uv run deploy.py` with the following args:

    - `index_type text_2_sql_schema_store`. This selects the `Text2SQLSchemaStoreAISearch` sub class.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.
    - `single_data_dictionary_file`. Optional parameter that controls whether you will be uploading a single data dictionary, or a data dictionary file per entity. By default, this is set to False.

### Column Value Store Index

**Execute the following commands in the `deploy_ai_search_indexes` directory:**

1. Create your `.env` file based on the provided sample `deploy_ai_search_indexes/.env.example`. Place this file in the same place in `deploy_ai_search_indexes/.env`.
2. Run `uv sync` within the `deploy_ai_search_indexes` directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.

**Execute the following commands in the `deploy_ai_search_indexes/src/deploy_ai_search_indexes` directory:**

3. Adjust `text_2_sql_column_value_store.py` with any changes to the index / indexer.
4. Run `uv run deploy.py` with the following args:

    - `index_type text_2_sql_column_value_store`. This selects the `Text2SQLColumnValueStoreAISearch` sub class.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.

### Query Cache Index

**Execute the following commands in the `deploy_ai_search_indexes` directory:**

1. Create your `.env` file based on the provided sample `deploy_ai_search_indexes/.env.example`. Place this file in the same place in `deploy_ai_search_indexes/.env`.
2. Run `uv sync` within the `deploy_ai_search_indexes` directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.

**Execute the following commands in the `deploy_ai_search_indexes/src/deploy_ai_search_indexes` directory:**

3. Adjust `text_2_sql_query_cache.py` with any changes to the index. **There is an optional provided indexer or skillset for this cache. You may instead want the application code will write directly to it. See the details in the Text2SQL README for different cache strategies.**
4. Run `uv run deploy.py` with the following args:

    - `index_type text_2_sql_query_cache`. This selects the `Text2SQLQueryCacheAISearch` sub class.
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.
    - `enable_cache_indexer`. Optional parameter that will enable the query cache indexer. Defaults to False.
    - `single_cache__file`. Optional parameter that controls whether you will be uploading a single data dictionary, or a data dictionary file per entity. By default, this is set to False.

## ai_search.py & environment.py

This includes a variety of helper files and scripts to deploy the index setup. This is useful for CI/CD to avoid having to write JSON files manually or use the UI to deploy the pipeline.
