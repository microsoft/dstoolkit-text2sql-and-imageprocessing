# Getting Started with Agentic Text2SQL Component

**Execute all these commands in the `text_2_sql` directory.**

To get started, perform the following steps:

1. Setup Azure OpenAI in your subscription with **gpt-4o-mini** & an embedding model, alongside a SQL Server sample database, AI Search and a storage account.
2. Clone this repository and deploy the AI Search text2sql indexes from `deploy_ai_search`.
3. Run `uv sync` within the text_2_sql directory to install dependencies.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`
    - See the supported connectors in `text_2_sql_core/src/text_2_sql_core/connectors`.
4. Create your `.env` file based on the provided sample `.env.example`. Place this file in the same place as the `.env.example`.
5. Generate a data dictionary for your target server using the instructions in the **Running** section of the `data_dictionary/README.md`.
6. Upload these generated data dictionaries files to the relevant containers in your storage account. Wait for them to be automatically indexed with the included skillsets.
7. Navigate to `autogen` directory to view the AutoGen implementation. Follow the steps in `Iteration 5 - Agentic Vector Based Text2SQL.ipynb` to get started.
