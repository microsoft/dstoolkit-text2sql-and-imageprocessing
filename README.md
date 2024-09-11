# Text2SQL and Image Processing in AI Search

This repo provides sample code for improving RAG applications with rich data sources including SQL Warehouses and documents analysed with Azure Document Intelligence.

It is intended that the plugins and skills provided in this repository, are adapted and added to your new or existing RAG application to improve the response quality.

## Components

- `./text_2_sql` contains an Multi-Shot implementation for Text2SQL generation and querying which can be used to answer questions backed by a database as a knowledge base.
- `./ai_search_with_adi_function_app` contains code for linking Azure Document Intelligence with AI Search to process complex documents with charts and images, and uses multi-modal models (gpt4o) to interpret and understand these.
- `./deploy_ai_search` provides an easy Python based utility for deploying an index, indexer and corresponding skillset for AI Search.

The above components have been successfully used on production RAG projects to increase the quality of responses. The code provided in this repo is a sample of the implementation and should be adjusted before being used in production.

## High Level Implementation

The following diagram shows a workflow for how the Text2SQL and AI Search plugin would be incorporated into a RAG application. Using the plugins available, alongside the Function Calling capabilities of LLMs, the LLM can do Chain of Thought reasoning to determine the steps needed to answer the question. This allows the LLM to recognise intent and therefore pick appropriate data sources based on the intent of the question, or a combination of both.

![High level workflow for a plugin driven RAG application](./images/Plugin%20Based%20RAG%20Flow.png "High Level Workflow")

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
