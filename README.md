# Text2SQL and Image Processing in AI Search

This repo provides sample code for improving RAG applications with rich data sources including SQL Warehouses and documents analysed with Azure Document Intelligence.

It is intended that the plugins and skills provided in this repository, are adapted and added to your new or existing RAG application to improve the response quality.

> [!IMPORTANT]
>
> - This repository now uses `uv` to manage dependencies and common utilities. See [uv](https://docs.astral.sh/uv/) for more details on how to get started.

## Components

- `./text_2_sql` contains an three Multi-Shot implementations for Text2SQL generation and querying which can be used to answer questions backed by a database as a knowledge base. A **prompt based** and **vector based** approach are shown, both of which exhibit great performance in answering sql queries. Additionally, a further iteration on the vector based approach is shown which uses a **query cache** to further speed up generation.  With these plugins, your RAG application can now access and pull data from any SQL table exposed to it to answer questions.
- `./image_processing` contains code for linking **Azure Document Intelligence** with AI Search to process complex documents with charts and images, and uses **multi-modal models (gpt4o)** to interpret and understand these. With this custom skill, the RAG application can **draw insights from complex charts** and images during the vector search. This function app also contains a **Semantic Text Chunking** method that aims to intelligently group similar sentences, retaining figures and tables together, whilst separating out distinct sentences.
- `./deploy_ai_search` provides an easy Python based utility for deploying an index, indexer and corresponding skillset for AI Search and for Text2SQL.

The above components have been successfully used on production RAG projects to increase the quality of responses.

> [!WARNING]
>
> - The code provided in this repo is a accelerator of the implementation and should be review / adjusted before being used in production.

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
