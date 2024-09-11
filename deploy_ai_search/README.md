# AI Search Indexing with Azure Document Intelligence - Pre-built Index Setup

The associated scripts in this portion of the repository contains pre-built scripts to deploy the skillset with Azure Document Intelligence.

## Steps

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication.
2. Adjust `rag_documents.py` with any changes to the index / indexer. The `get_skills()` method implements the skills pipeline. Make any adjustments here in the skills needed to enrich the data source.
3. Run `deploy.py` with the following args:

    - `indexer_type rag`. This selects the `rag_documents` sub class.
    - `enable_page_chunking True`. This determines whether page wise chunking is applied in ADI, or whether the inbuilt skill is used for TextSplit. **Page wise analysis in ADI is recommended to avoid splitting tables / figures across multiple chunks, when the chunking is performed.**
    - `rebuild`. Whether to delete and rebuild the index.
    - `suffix`. Optional parameter that will apply a suffix onto the deployed index and indexer. This is useful if you want deploy a test version, before overwriting the main version.

## ai_search.py & environment.py

This includes a variety of helper files and scripts to deploy the index setup. This is useful for CI/CD to avoid having to write JSON files manually or use the UI to deploy the pipeline.
