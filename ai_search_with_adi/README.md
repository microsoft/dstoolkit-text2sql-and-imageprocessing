# AI Search Indexing with Azure Document Intelligence

This portion of the repo contains code for linking Azure Document Intelligence with AI Search to process complex documents with charts and images, and uses multi-modal models (gpt4o) to interpret and understand these.

The implementation in Python, although it can easily be adapted for C# or another language. The code is designed to run in an Azure Function App inside the tenant.

**This approach makes use of Azure Document Intelligence v4.0 which is still in preview.**

## High Level Workflow

A common way to perform document indexing, is to either extract the text content or use [optical character recognition](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-ocr) to gather the text content before indexing. Whilst this works well for simple files that contain mainly text based information, the response quality diminishes significantly when the documents contain mainly charts and images, such as a PowerPoint presentation.

To solve this issue and to ensure that good quality information is extracted from the document, an indexer using [Azure Document Intelligence (ADI)](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/overview?view=doc-intel-4.0.0) is developed with [Custom Skills](https://learn.microsoft.com/en-us/azure/search/cognitive-search-custom-skill-web-api):

![High level workflow for indexing with Azure Document Intelligence based skills](./images/Indexing%20vs%20Indexing%20with%20ADI.png "Indexing with Azure Document Intelligence Approach")

Instead of using OCR to extract the contents of the document, ADIv4 is used to analyse the layout of the document and convert it to a Markdown format. The Markdown format brings benefits such as:

- Table layout
- Section and header extraction with Markdown headings
- Figure and image extraction

Once the Markdown is obtained, several steps are carried out:

1. **Extraction of images / charts**. The figures identified are extracted from the original document and passed to a multi-modal model (gpt4o in this case) for analysis. We obtain a description and summary of the chart / image to infer the meaning of the figure. This allows us to index and perform RAG analysis the information that is visually obtainable from a chart, without it being explicitly mentioned in the text surrounding. The information is added back into the original chart.

2. **Extraction of sections and headers**. The sections and headers are extracted from the document and returned additionally to the indexer under a separate field. This allows us to store them as a separate field in the index and therefore surface the most relevant chunks.

3. **Cleaning of Markdown**. The final markdown content is cleaned of any characters or unsupported Markdown elements that we do not want in the chunk e.g. non-relevant images.

Page wise analysis in ADI is used to avoid splitting tables / figures across multiple chunks, when the chunking is performed.

The properties returned from the ADI Custom Skill are then used to perform the following skills:

- Pre-vectorisation cleaning
- Keyphrase extraction
- Vectorisation

## Provided Notebooks \& Utilities

- `./ai_search.py`, `./deploy.py` provide an easy Python based utility for deploying an index, indexer and corresponding skillset for AI Search.
- `./function_apps/indexer` provides a pre-built Python function app that communicates with Azure Document Intelligence, Azure OpenAI etc to perform the Markdown conversion, extraction of figures, figure understanding and corresponding cleaning of Markdown.
- `./rag_with_ai_search.ipynb` provides example of how to utilise the AI Search plugin to query the index.

## Deploying AI Search Setup

To deploy the pre-built index and associated indexer / skillset setup, see instructions in `./ai_search/README.md`.

## ADI Custom Skill

Deploy the associated function app and required resources. You can then experiment with the custom skill by sending an HTTP request in the AI Search JSON format to the `/adi_2_ai_search` HTTP endpoint.

To use with an index, either use the utility to configure a indexer in the provided form, or integrate the skill with your skillset pipeline.

### function_app.py

`./function_apps/indexer/function_app.py` contains the HTTP entrypoints for the ADI skill and the other provided utility skills.

### adi_2_aisearch

`./function_apps/indexer/adi_2_aisearch.py` contains the methods for content extraction with ADI. The key methods are:

#### analyse_document

This method takes the passed file, uploads it to ADI and retrieves the Markdown format.

#### process_figures_from_extracted_content

This method takes the detected figures, and crops them out of the page to save them as images. It uses the `understand_image_with_vlm` to communicate with Azure OpenAI to understand the meaning of the extracted figure.

`update_figure_description` is used to update the original Markdown content with the description and meaning of the figure.

#### clean_adi_markdown

This method performs the final cleaning of the Markdown contents. In this method, the section headings and page numbers are extracted for the content to be returned to the indexer.

### Input Format

The ADI Skill conforms to the [Azure AI Search Custom Skill Input Format](https://learn.microsoft.com/en-gb/azure/search/cognitive-search-custom-skill-web-api?WT.mc_id=Portal-Microsoft_Azure_Search#sample-input-json-structure). AI Search will automatically build this format if you use the utility file provided in this repo to build your indexer and skillset.

```json
{
    "values": [
        {
            "recordId": "0",
            "data": {
                "source": "<FULL URI TO BLOB>"
            }
        },
        {
            "recordId": "1",
            "data": {
                "source": "<FULL URI TO BLOB>"
            }
        }
    ]
}
```

### Output Format

The ADI Skill conforms to the [Azure AI Search Custom Skill Output Format](https://learn.microsoft.com/en-gb/azure/search/cognitive-search-custom-skill-web-api?WT.mc_id=Portal-Microsoft_Azure_Search#sample-output-json-structure).

If `chunk_by_page` header is `True` (recommended):

```json
{
    "values": [
        {
            "recordId": "0",
            "data": {
                "extracted_content": [
                    {
                        "page_number": 1,
                        "sections": [
                            "<LIST OF DETECTED HEADINGS AND SECTIONS FOR PAGE NUMBER 1>"
                        ],
                        "content": "<CLEANED MARKDOWN CONTENT FOR PAGE NUMBER 1>"
                    },
                    {
                        "page_number": 2,
                        "sections": [
                            "<LIST OF DETECTED HEADINGS AND SECTIONS FOR PAGE NUMBER 2>"
                        ],
                        "content": "<CLEANED MARKDOWN CONTENT FOR PAGE NUMBER 2>"
                    }
                ]
            }
        },
        {
            "recordId": "1",
            "data": {
                "extracted_content": [
                    {
                        "page_number": 1,
                        "sections": [
                            "<LIST OF DETECTED HEADINGS AND SECTIONS FOR PAGE NUMBER 1>"
                        ],
                        "content": "<CLEANED MARKDOWN CONTENT FOR PAGE NUMBER 2>"
                    },
                    {
                        "page_number": 2,
                        "sections": [
                            "<LIST OF DETECTED HEADINGS AND SECTIONS FOR PAGE NUMBER 1>"
                        ],
                        "content": "<CLEANED MARKDOWN CONTENT FOR PAGE NUMBER 2>"
                    }
                ]
            }
        }
    ]
}
```

If `chunk_by_page` header is `False`:

```json
{
    "values": [
        {
            "recordId": "0",
            "data": {
                "extracted_content": {
                    "sections": [
                        "<LIST OF DETECTED HEADINGS AND SECTIONS FOR THE ENTIRE DOCUMENT>"
                    ],
                    "content": "<CLEANED MARKDOWN CONTENT FOR THE ENTIRE DOCUMENT>"
                }
            }
        },
        {
            "recordId": "1",
            "data": {
                "extracted_content": {
                    "sections": [
                        "<LIST OF DETECTED HEADINGS AND SECTIONS FOR THE ENTIRE DOCUMENT>"
                    ],
                    "content": "<CLEANED MARKDOWN CONTENT FOR THE ENTIRE DOCUMENT>"
                }
            }
        }
    ]
}
```

**Page wise analysis in ADI is recommended to avoid splitting tables / figures across multiple chunks, when the chunking is performed.**


## Production Considerations

Below are some of the considerations that should be made before using this custom skill in production:

- This approach makes use of Azure Document Intelligence v4.0 which is still in preview. Features may change before the GA release. ADI v4.0 preview is only available in select regions.
- Azure Document Intelligence output quality varies significantly by file type. A PDF file type will producer richer outputs in terms of figure detection etc, compared to a PPTX file in our testing.

## Possible Improvements

Below are some possible improvements that could be made to the vectorisation approach:

- Storing the extracted figures in blob storage for access later. This would allow the LLM to resurface the correct figure or provide a link to the give in the reference system to be displayed in the UI.
