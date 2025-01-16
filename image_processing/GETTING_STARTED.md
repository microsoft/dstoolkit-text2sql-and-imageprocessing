# Getting Started with Document Intelligence Function App

To get started, perform the following steps:

1. Setup Azure OpenAI in your subscription with **gpt-4o-mini** & an embedding model, an Python Function App, AI Search and a storage account.
2. Clone this repository and deploy the AI Search rag documents indexes from `deploy_ai_search`.
3. Run `uv sync` within the image_processing directory to install dependencies (or used the synced `requirements.txt`)
4. Use the `.env.example` to add the required environmental variables to your function app. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication. Use this template to update the environment variables in the function app.
5. [Package your Azure Function and upload to your Function App.](https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies?tabs=windows) and test with a HTTP request.
6. Upload a document for indexing or send a direct HTTP request to the Azure Function.
