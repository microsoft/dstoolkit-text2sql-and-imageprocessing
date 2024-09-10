# AI Search Indexing with Azure Document Intelligence - Function App Setup

The associated scripts in this portion of the repository contains the Azure Document Intelligence powered Function app.

## Steps

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication. Use this template to update the environment variables in the function app.
2. Make sure the infra and required identities are setup. This setup requires Azure Document Intelligence and GPT4o.
3. [Deploy your function app](https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies?tabs=windows) and test with a HTTP request.

## Code Files

### function_app.py

`./indexer/adi_function_app.py` contains the HTTP entrypoints for the ADI skill and the other provided utility skills.

### adi_2_aisearch

`./indexer/adi_2_aisearch.py` contains the methods for content extraction with ADI. The key methods are:

#### analyse_document

This method takes the passed file, uploads it to ADI and retrieves the Markdown format.

#### process_figures_from_extracted_content

This method takes the detected figures, and crops them out of the page to save them as images. It uses the `understand_image_with_vlm` to communicate with Azure OpenAI to understand the meaning of the extracted figure.

`update_figure_description` is used to update the original Markdown content with the description and meaning of the figure.

#### clean_adi_markdown

This method performs the final cleaning of the Markdown contents. In this method, the section headings and page numbers are extracted for the content to be returned to the indexer.

## Input Format

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

## Output Format

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
