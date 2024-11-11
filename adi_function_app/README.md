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

2. **Cleaning of Markdown**. The final markdown content is cleaned of any characters or unsupported Markdown elements that we do not want in the chunk e.g. non-relevant images.

Page wise analysis in ADI is used to avoid splitting tables / figures across multiple chunks, when the chunking is performed.

The properties returned from the ADI Custom Skill are then used to perform the following skills:

- Pre-vectorisation cleaning. This stage is important as we extract the section information in this step from the headers in the document. Additionally, we remove any Markdown tags or characters that would cause an embedding error.
- Keyphrase extraction
- Vectorisation

## Sample Output

Using the [Phi-3 Technical Report: A Highly Capable Language Model Locally on Your Phone](https://arxiv.org/pdf/2404.14219) as an example, the following output can be obtained for page 7:

```json
{
    "content": "\n<table>\n<caption>Table 1: Comparison results on RepoQA benchmark.</caption>\n<tr>\n<th>Model</th>\n<th>Ctx Size</th>\n<th>Python</th>\n<th>C++</th>\n<th>Rust</th>\n<th>Java</th>\n<th>TypeScript</th>\n<th>Average</th>\n</tr>\n<tr>\n<td>gpt-4O-2024-05-13</td>\n<td>128k</td>\n<td>95</td>\n<td>80</td>\n<td>85</td>\n<td>96</td>\n<td>97</td>\n<td>90.6</td>\n</tr>\n<tr>\n<td>gemini-1.5-flash-latest</td>\n<td>1000k</td>\n<td>93</td>\n<td>79</td>\n<td>87</td>\n<td>94</td>\n<td>97</td>\n<td>90</td>\n</tr>\n<tr>\n<td>Phi-3.5-MoE</td>\n<td>128k</td>\n<td>89</td>\n<td>74</td>\n<td>81</td>\n<td>88</td>\n<td>95</td>\n<td>85</td>\n</tr>\n<tr>\n<td>Phi-3.5-Mini</td>\n<td>128k</td>\n<td>86</td>\n<td>67</td>\n<td>73</td>\n<td>77</td>\n<td>82</td>\n<td>77</td>\n</tr>\n<tr>\n<td>Llama-3.1-8B-Instruct</td>\n<td>128k</td>\n<td>80</td>\n<td>65</td>\n<td>73</td>\n<td>76</td>\n<td>63</td>\n<td>71</td>\n</tr>\n<tr>\n<td>Mixtral-8x7B-Instruct-v0.1</td>\n<td>32k</td>\n<td>66</td>\n<td>65</td>\n<td>64</td>\n<td>71</td>\n<td>74</td>\n<td>68</td>\n</tr>\n<tr>\n<td>Mixtral-8x22B-Instruct-v0.1</td>\n<td>64k</td>\n<td>60</td>\n<td>67</td>\n<td>74</td>\n<td>83</td>\n<td>55</td>\n<td>67.8</td>\n</tr>\n</table>\n\n\nsuch as Arabic, Chinese, Russian, Ukrainian, and Vietnamese, with average MMLU-multilingual scores\nof 55.4 and 47.3, respectively. Due to its larger model capacity, phi-3.5-MoE achieves a significantly\nhigher average score of 69.9, outperforming phi-3.5-mini.\n\nMMLU(5-shot) MultiLingual\n\nPhi-3-mini\n\nPhi-3.5-mini\n\nPhi-3.5-MoE\n\n\n<!-- FigureContent=\"**Technical Analysis of Figure 4: Comparison of phi-3-mini, phi-3.5-mini and phi-3.5-MoE on MMLU-Multilingual tasks**\n\n1. **Overview:**\n   - The image is a bar chart comparing the performance of three different models—phi-3-mini, phi-3.5-mini, and phi-3.5-MoE—on MMLU-Multilingual tasks across various languages.\n\n2. **Axes:**\n   - The x-axis represents the languages in which the tasks were performed. The languages listed are: Arabic, Chinese, Dutch, French, German, Italian, Russian, Spanish, Ukrainian, Vietnamese, and English.\n   - The y-axis represents the performance, likely measured in percentage or score, ranging from 0 to 90.\n\n3. **Legend:**\n   - The chart uses three different colors to represent the three models:\n     - Orange bars represent the phi-3-mini model.\n     - Green bars represent the phi-3.5-mini model.\n     - Blue bars represent the phi-3.5-MoE model.\n\n4. **Data Interpretation:**\n   - Across all languages, the phi-3.5-MoE (blue bars) consistently outperforms the other two models, showing the highest bars.\n   - The phi-3.5-mini (green bars) shows better performance than the phi-3-mini (orange bars) in most languages, but not at the level of phi-3.5-MoE.\n\n5. **Language-specific Insights:**\n   - **Arabic**: phi-3.5-MoE shows significantly higher performance compared to the other two models, with phi-3.5-mini outperforming phi-3-mini.\n   - **Chinese**: A similar trend is observed as in Arabic, with phi-3.5-MoE leading by a wide margin.\n   - **Dutch**: Performance is roughly similar between phi-3.5-mini and phi-3.5-MoE, with phi-3.5-MoE being slightly better.\n   - **French**: A clear distinction in performance, with phi-3.5-MoE far exceeding the other two.\n   - **German**: phi-3.5-MoE leads, followed by phi-3.5-mini, while phi-3-mini lags significantly behind.\n   - **Italian**: The performance gap narrows between phi-3.5-mini and phi-3.5-MoE, but the latter is still superior.\n   - **Russian**: phi-3.5-MoE shows noticeably higher performance.\n   - **Spanish**: The performance trend is consistent with the previous languages, with phi-3.5-MoE leading.\n   - **Ukrainian**: A substantial lead by phi-3.5-MoE.\n   - **Vietnamese**: An anomaly where all models show closer performance, yet phi-3.5-MoE still leads.\n   - **English**: The highest performance is seen in English, with phi-3.5-MoE nearly reaching the maximum score.\n\n6. **Conclusion:**\n   - The phi-3.5-MoE model consistently outperforms the phi-3-mini and phi-3.5-mini models across all MMLU-Multilingual tasks.\n   - The phi-3.5-mini model shows a general improvement over the phi-3-mini, but the improvement is not as significant as phi-3.5-MoE.\n\nThis structured analysis provides a comprehensive understanding of the comparative performance of the mentioned models across multilingual tasks.\" -->\n\n\n We evaluate the phi-3.5-mini and phi-3.5-MoE models on two long-context understanding tasks:\nRULER [HSK+24] and RepoQA [LTD+24]. As shown in Tables 1 and 2, both phi-3.5-MoE and phi-\n3.5-mini outperform other open-source models with larger sizes, such as Llama-3.1-8B, Mixtral-8x7B,\nand Mixtral-8x22B, on the RepoQA task, and achieve comparable performance to Llama-3.1-8B on\nthe RULER task. However, we observe a significant performance drop when testing the 128K context\nwindow on the RULER task. We suspect this is due to the lack of high-quality long-context data in\nmid-training, an issue we plan to address in the next version of the model release.\n\n In the table 3, we present a detailed evaluation of the phi-3.5-mini and phi-3.5-MoE models\ncompared with recent SoTA pretrained language models, such as GPT-4o-mini, Gemini-1.5 Flash, and\nopen-source models like Llama-3.1-8B and the Mistral models. The results show that phi-3.5-mini\nachieves performance comparable to much larger models like Mistral-Nemo-12B and Llama-3.1-8B, while\nphi-3.5-MoE significantly outperforms other open-source models, offers performance comparable to\nGemini-1.5 Flash, and achieves above 90% of the average performance of GPT-4o-mini across various\nlanguage benchmarks.\n\n\n\n\n",
    "page_number": 7
}
```

The Figure 4 content has been interpreted and added into the extracted chunk to enhance the context for a RAG application. This is particularly powerful for applications where the documents are heavily imaged or chart based.

## Provided Notebooks \& Utilities

- `./ai_search_with_adi_function_app` provides a pre-built Python function app that communicates with Azure Document Intelligence, Azure OpenAI etc to perform the Markdown conversion, extraction of figures, figure understanding and corresponding cleaning of Markdown.
- `./rag_with_ai_search.ipynb` provides example of how to utilise the AI Search plugin to query the index.

## Deploying AI Search Setup

To deploy the pre-built index and associated indexer / skillset setup, see instructions in `./deploy_ai_search/README.md`.

## ADI Custom Skill

Deploy the associated function app and required resources. You can then experiment with the custom skill by sending an HTTP request in the AI Search JSON format to the `/adi_2_ai_search` HTTP endpoint.

To use with an index, either use the utility to configure a indexer in the provided form, or integrate the skill with your skillset pipeline.

### Deployment Steps

1. Update `.env` file with the associated values. Not all values are required dependent on whether you are using System / User Assigned Identities or a Key based authentication. Use this template to update the environment variables in the function app.
2. Make sure the infra and required identities are setup. This setup requires Azure Document Intelligence and GPT4o.
3. [Deploy your function app](https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies?tabs=windows) and test with a HTTP request.

### Code Files

#### function_app.py

`./indexer/ai_search_with_adi_function_app.py` contains the HTTP entrypoints for the ADI skill and the other provided utility skills.

#### adi_2_aisearch

`./indexer/adi_2_aisearch.py` contains the methods for content extraction with ADI. The key methods are:

##### analyse_document

This method takes the passed file, uploads it to ADI and retrieves the Markdown format.

##### process_figures_from_extracted_content

This method takes the detected figures, and crops them out of the page to save them as images. It uses the `understand_image_with_vlm` to communicate with Azure OpenAI to understand the meaning of the extracted figure.

`update_figure_description` is used to update the original Markdown content with the description and meaning of the figure.

##### build_and_clean_markdown_for_response

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
                        "content": "<CLEANED MARKDOWN CONTENT FOR PAGE NUMBER 1>"
                    },
                    {
                        "page_number": 2,
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
                        "content": "<CLEANED MARKDOWN CONTENT FOR PAGE NUMBER 2>"
                    },
                    {
                        "page_number": 2,
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
                    "content": "<CLEANED MARKDOWN CONTENT FOR THE ENTIRE DOCUMENT>"
                }
            }
        },
        {
            "recordId": "1",
            "data": {
                "extracted_content": {
                    "content": "<CLEANED MARKDOWN CONTENT FOR THE ENTIRE DOCUMENT>"
                }
            }
        }
    ]
}
```

**Page wise analysis in ADI is recommended to avoid splitting tables / figures across multiple chunks, when the chunking is performed.**

## Other Provided Custom Skills

Due to a AI Search product limitation that AI Search cannot connect to AI Services behind Private Endpoints, we provide a Custom Key Phrase Extraction Skill that will work within a Private Endpoint environment.

Additionally, a custom cleaning skill is provided to clean the chunks before vectorisation takes place.

## Production Considerations

Below are some of the considerations that should be made before using this custom skill in production:

- This approach makes use of Azure Document Intelligence v4.0 which is still in preview. Features may change before the GA release. ADI v4.0 preview is only available in select regions.
- Azure Document Intelligence output quality varies significantly by file type. A PDF file type will producer richer outputs in terms of figure detection etc, compared to a PPTX file in our testing.

## Possible Improvements

Below are some possible improvements that could be made to the vectorisation approach:

- Storing the extracted figures in blob storage for access later. This would allow the LLM to resurface the correct figure or provide a link to the give in the reference system to be displayed in the UI.
