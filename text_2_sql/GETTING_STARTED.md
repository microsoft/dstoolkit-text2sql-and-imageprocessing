# Getting Started with Agentic Text2SQL Component

To get started, perform the following steps:

**Execute the following commands in the `deploy_ai_search_indexes` directory:**

1. Setup Azure OpenAI in your subscription with **gpt-4o-mini** & an embedding model, alongside a SQL Server sample database, AI Search and a storage account.
2. Clone this repository and deploy the AI Search text2sql indexes from `deploy_ai_search_indexes`. See the instructions in the **Steps for Text2SQL Index Deployment (For Structured RAG)** section of the `deploy_ai_search_indexes/README.md`.
3. Create your `.env` file based on the provided sample `deploy_ai_search_indexes/.env.example`. Place this file in the same place in `deploy_ai_search_indexes/.env`.

**Execute the following commands in the `text_2_sql_core` directory:**

4. Create your `.env` file based on the provided sample `text_2_sql/.env.example`. Place this file in the same place in `text_2_sql/.env`.
5. Run `uv sync` within the `text_2_sql_core` directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.
6. Create your `.env` file based on the provided sample `text_2_sql/.env.example`. Place this file in the same place in `text_2_sql/.env`.
7. Generate a data dictionary for your target server using the instructions in the **Running** section of the `data_dictionary/README.md`.
8. Upload these generated data dictionaries files to the relevant containers in your storage account. Wait for them to be automatically indexed with the included skillsets.

**Execute the following commands in the `autogen` directory:**

9. Run `uv sync` within the `autogen` directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.
10. Navigate to `autogen` directory to view the AutoGen implementation. Follow the steps in `Iteration 5 - Agentic Vector Based Text2SQL.ipynb` to get started.
