# Getting Started with Document Intelligence Function App

To get started, perform the following steps:

1. Setup Azure OpenAI in your subscription with **gpt-4o-mini** & an embedding model, an Python Function App, AI Search and a storage account.
2. Clone this repository and deploy the AI Search rag documents indexes from `deploy_ai_search`.
3. Run `uv sync` within the image_processing directory to install dependencies.
4. Configure the environment variables of the function app based on the provided sample
5. Package your Azure Function and upload to your Function App
6. Upload a document for indexing or send a direct HTTP request to the Azure Function.
