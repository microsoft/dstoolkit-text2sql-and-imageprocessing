# Getting Started with Agentic Text2SQL Component

To get started, perform the following steps:

1. Setup Azure OpenAI in your subscription with **gpt-4o-mini** & an embedding model, alongside a SQL Server sample database, AI Search and a storage account.
2. Clone this repository and deploy the AI Search text2sql indexes from `deploy_ai_search`.
3. Run `uv sync` within the text_2_sql directory to install dependencies.
4. Create your `.env` file based on the provided sample `.env.example`. Place this file in the same place as the `.env.example`.
5. Generate a data dictionary for your target server using the instructions in `data_dictionary`.
6. Upload these data dictionaries to the relevant containers in your storage account. Wait for them to be automatically indexed with the included skillsets.
7. Navigate to `autogen` directory to view the AutoGen implementation. Follow the steps in `Iteration 5 - Agentic Vector Based Text2SQL.ipynb` to get started.
