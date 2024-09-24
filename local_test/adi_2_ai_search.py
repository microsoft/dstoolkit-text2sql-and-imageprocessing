# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import base64
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeResult,
    ContentFormat,
    AnalyzeOutputOption,
)
import os
import re
import asyncio
import logging
from storage_account import StorageAccountHelper
import concurrent.futures
import json
from openai import AsyncAzureOpenAI
from typing import Union
import openai
from environment import IdentityType, get_identity_type


def build_and_clean_markdown_for_response(
    markdown_text: str,
    figures: dict,
    page_no: int = None,
    remove_irrelevant_figures=False,
):
    """Clean Markdown text extracted by the Azure Document Intelligence service.

    Args:
    -----
        markdown_text (str): The original Markdown text.
        remove_irrelevant_figures (bool): Whether to remove all figures or just irrelevant ones.

    Returns:
    --------
        str: The cleaned Markdown text.
    """

    output_dict = {}
    comment_patterns = r"<!-- PageNumber=\"[^\"]*\" -->|<!-- PageHeader=\"[^\"]*\" -->|<!-- PageFooter=\"[^\"]*\" -->|<!-- PageBreak -->"
    cleaned_text = re.sub(comment_patterns, "", markdown_text, flags=re.DOTALL)

    # Remove irrelevant figures
    if remove_irrelevant_figures:
        irrelevant_figure_pattern = r"<!-- FigureContent=\"Irrelevant Image\" -->\s*"
        cleaned_text = re.sub(
            irrelevant_figure_pattern, "", cleaned_text, flags=re.DOTALL
        )

    logging.info(f"Cleaned Text: {cleaned_text}")

    markdown_without_figure_content = re.sub(
        r"<!-- FigureContent=\"[^\"]*\" -->", "", cleaned_text, flags=re.DOTALL
    )

    combined_pattern = r"(.*?)\n===|\n#+\s*(.*?)\n"
    doc_metadata = re.findall(
        combined_pattern, markdown_without_figure_content, re.DOTALL
    )
    doc_metadata = [match for group in doc_metadata for match in group if match]

    output_dict["content"] = cleaned_text
    output_dict["sections"] = doc_metadata

    output_dict["figures"] = figures

    # add page number when chunk by page is enabled
    if page_no is not None:
        output_dict["pageNumber"] = page_no

    return output_dict


def update_figure_description(
    md_content: str, figure_id: str, img_description: str, offset: int, length: int
):
    """
    Updates the figure description in the Markdown content.

    Args:
        md_content (str): The original Markdown content.
        img_description (str): The new description for the image.
        offset (int): Position offset in the text.
        length (int): Length of the original figure in the text.

    Returns:
        str: The updated Markdown content with the new figure description.
    """

    # Define the new string to replace the old content
    new_string = f'<!-- FigureId="{figure_id}" FigureContent="{img_description}" -->'

    # Calculate the end index of the content to be replaced
    end_index = offset + length

    # Ensure that the end_index does not exceed the length of the Markdown content
    if end_index > len(md_content):
        end_index = len(md_content)

    # Replace the old string with the new string
    new_md_content = md_content[:offset] + new_string + md_content[end_index:]

    return new_md_content, len(new_string)


async def understand_image_with_gptv(image_base64, caption, tries_left=3):
    """
    Generates a description for an image using the GPT-4V model.

    Parameters:
    - image_base64 (str): image file.
    - caption (str): The caption for the image.

    Returns:
    - img_description (str): The generated description for the image.
    """

    MAX_TOKENS = 2000
    api_version = os.environ["OpenAI__ApiVersion"]
    model = os.environ["OpenAI__MultiModalDeployment"]

    if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        api_key = None
    elif get_identity_type() == IdentityType.USER_ASSIGNED:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(
                managed_identity_client_id=os.environ["FunctionApp__ClientId"]
            ),
            "https://cognitiveservices.azure.com/.default",
        )
        api_key = None
    else:
        token_provider = None
        api_key = os.environ["OpenAI__ApiKey"]

    system_prompt = """You are an expert in technical image analysis. Your task is to provided analysis of images. You should FOCUS on what info can be inferred from the image and the meaning of the data inside the image. Draw actionable insights and conclusions from the image. Do not describe the image in a general way or describe the image in a way that is not useful for decision-making.

    If the image is a chart for instance, you should describe the data trends, patterns, and insights that can be drawn from the chart. For example, you could describe the increase or decrease in sales over time, the peak sales period, or the sales performance of a particular product.

    If the image is a map, you should describe the geographical features, landmarks, and any other relevant information that can be inferred from the map.

    If the image is a diagram, you should describe the components, relationships, and any other relevant information that can be inferred from the diagram.

    Include any data points, labels, and other relevant information that can be inferred from the image.

    Provide a well-structured, detailed, and actionable analysis of the image. Focus on extracting data and information that can be inferred from the image.

    IMPORTANT: If the provided image is a logo or photograph, simply return 'Irrelevant Image'."""

    user_input = "Perform technical analysis on this image. Provide a well-structured, description."

    if caption is not None and len(caption) > 0:
        user_input += f" (note: it has the following caption: {caption})"

    try:
        async with AsyncAzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_ad_token_provider=token_provider,
            azure_endpoint=os.environ.get("OpenAI__Endpoint"),
        ) as client:
            # We send both image caption and the image body to GPTv for better understanding
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_input,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=MAX_TOKENS,
            )

            logging.info(f"Response: {response}")

            img_description = response.choices[0].message.content

            logging.info(f"Image Description: {img_description}")

        return img_description
    except openai.RateLimitError as e:
        logging.error("OpenAI Rate Limit Error: %s", e)

        if tries_left > 0:
            logging.info(
                "Retrying understanding of image with %s tries left.", tries_left
            )
            remaining_tries = tries_left - 1
            backoff = 20 ** (3 - remaining_tries)
            await asyncio.sleep(backoff)
            return await understand_image_with_gptv(
                image_base64, caption, tries_left=remaining_tries
            )
        else:
            raise Exception("OpenAI Rate Limit Error: No retries left.") from e
    except (openai.OpenAIError, openai.APIConnectionError) as e:
        logging.error("OpenAI Error: %s", e)

        raise Exception("OpenAI Connection Error: No retries left.") from e


async def download_figure_image(
    model_id: str, operation_id: str, figure_id: str
) -> bytearray:
    """Download the image associated with a figure extracted by the Azure Document Intelligence service.

    Args:
    -----
        model_id (str): The model ID used for the analysis.
        operation_id (str): The operation ID of the analysis.
        figure_id (str): The ID of the figure to download.

    Returns:
    --------
        bytes: The image associated with the figure."""
    document_intelligence_client = await get_document_intelligence_client()
    async with document_intelligence_client:
        response = await document_intelligence_client.get_analyze_result_figure(
            model_id=model_id, result_id=operation_id, figure_id=figure_id
        )

        full_bytes = bytearray()
        async for chunk in response:
            full_bytes.extend(chunk)

    return full_bytes


async def process_figures_from_extracted_content(
    result: AnalyzeResult,
    operation_id: str,
    container_and_blob: str,
    markdown_content: str,
    page_number: None | int = None,
    page_offset: int = 0,
) -> Union[str, dict]:
    """Process the figures extracted from the content using ADI and send them for analysis.

    Args:
    -----
        result (AnalyzeResult): The result of the document analysis.
        operation_id (str): The operation ID of the analysis.
        container_and_blob (str): The container and blob of the document.
        markdown_content (str): The extracted content in Markdown format.
        page_number (int): The page number to process. If None, all pages are processed.
        page_offset (int): The offset of the page.

    Returns:
    --------
        str: The updated Markdown content with the figure descriptions.
        dict: A mapping of the FigureId to the stored Uri in blob storage."""

    figure_processing_datas = []
    download_image_tasks = []
    figure_understanding_tasks = []
    figure_upload_tasks = []

    if result.figures:
        for figure in result.figures:
            if figure.id is None:
                continue

            for region in figure.bounding_regions:
                if page_number is not None and region.page_number != page_number:
                    continue

                logging.info(f"Figure ID: {figure.id}")
                download_image_tasks.append(
                    download_figure_image(
                        model_id=result.model_id,
                        operation_id=operation_id,
                        figure_id=figure.id,
                    )
                )

                container, blob = container_and_blob
                image_blob = f"{blob}/{figure.id}.png"

                caption = figure.caption.content if figure.caption is not None else None

                logging.info(f"Figure Caption: {caption}")

                figure_processing_datas.append(
                    (figure.id, container, image_blob, caption, figure.spans[0])
                )

                break

    logging.info("Running image download tasks")
    image_responses = await asyncio.gather(*download_image_tasks)
    logging.info("Finished image download tasks")

    storage_account_helper = await get_storage_account_helper()

    for figure_processing_data, response in zip(
        figure_processing_datas, image_responses
    ):
        _, container, image_blob, caption, _ = figure_processing_data
        base_64_image = base64.b64encode(response).decode("utf-8")

        logging.info(f"Image Blob: {image_blob}")

        figure_understanding_tasks.append(
            understand_image_with_gptv(base_64_image, caption)
        )

        image_data = base64.b64decode(base_64_image)

        figure_upload_tasks.append(
            storage_account_helper.upload_blob(
                container, image_blob, image_data, "image/png"
            )
        )

    figure_ids = [
        figure_processing_data[0] for figure_processing_data in figure_processing_datas
    ]
    logging.info("Running image understanding tasks")
    figure_descriptions = await asyncio.gather(*figure_understanding_tasks)
    logging.info("Finished image understanding tasks")
    logging.info(f"Image Descriptions: {figure_descriptions}")

    logging.info("Running image upload tasks")
    figure_uris = await asyncio.gather(*figure_upload_tasks)
    logging.info("Finished image upload tasks")

    figures = [
        {"figureId": figure_id, "figureUri": figure_uri}
        for figure_id, figure_uri in zip(figure_ids, figure_uris)
    ]

    running_offset = 0
    for figure_processing_data, figure_description in zip(
        figure_processing_datas, figure_descriptions
    ):
        figure_id, _, _, _, figure_span = figure_processing_data
        starting_offset = figure_span.offset + running_offset - page_offset
        markdown_content, desc_offset = update_figure_description(
            markdown_content,
            figure_id,
            figure_description,
            starting_offset,
            figure_span.length,
        )
        running_offset += desc_offset

    return markdown_content, figures


def create_page_wise_content(result: AnalyzeResult) -> list:
    """Create a list of page-wise content extracted by the Azure Document Intelligence service.

    Args:
    -----
        result (AnalyzeResult): The result of the document analysis.

    Returns:
    --------
        list: A list of page-wise content extracted by the Azure Document Intelligence service.
    """

    page_wise_content = []
    page_numbers = []
    page_offsets = []

    for page in result.pages:
        page_content = result.content[
            page.spans[0]["offset"] : page.spans[0]["offset"] + page.spans[0]["length"]
        ]
        page_wise_content.append(page_content)
        page_numbers.append(page.page_number)
        page_offsets.append(page.spans[0]["offset"])

    return page_wise_content, page_numbers, page_offsets


async def get_document_intelligence_client() -> DocumentIntelligenceClient:
    """Get the Azure Document Intelligence client.

    Returns:
    --------
        DocumentIntelligenceClient: The Azure Document Intelligence client."""
    if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
        credential = DefaultAzureCredential()
    elif get_identity_type() == IdentityType.USER_ASSIGNED:
        credential = DefaultAzureCredential(
            managed_identity_client_id=os.environ["FunctionApp__ClientId"]
        )
    else:
        credential = AzureKeyCredential(
            os.environ["AIService__DocumentIntelligence__Key"]
        )

    return DocumentIntelligenceClient(
        endpoint=os.environ["AIService__DocumentIntelligence__Endpoint"],
        credential=credential,
    )


async def get_storage_account_helper() -> StorageAccountHelper:
    """Get the Storage Account Helper.

    Returns:
    --------
        StorageAccountHelper: The Storage Account Helper."""

    return StorageAccountHelper()


async def analyse_document(file_path: str) -> tuple[AnalyzeResult, str]:
    """Analyse a document using the Azure Document Intelligence service.

    Args:
    -----
        file_path (str): The path to the document to analyse.

    Returns:
    --------
        AnalyzeResult: The result of the document analysis.
        str: The operation ID of the analysis.
    """
    with open(file_path, "rb") as f:
        file_read = f.read()

    document_intelligence_client = await get_document_intelligence_client()
    async with document_intelligence_client:
        poller = await document_intelligence_client.begin_analyze_document(
            model_id="prebuilt-layout",
            analyze_request=file_read,
            output_content_format=ContentFormat.MARKDOWN,
            output=[AnalyzeOutputOption.FIGURES],
            content_type="application/octet-stream",
        )

        result = await poller.result()

        operation_id = poller.details["operation_id"]

    if result is None or result.content is None or result.pages is None:
        raise ValueError(
            "Failed to analyze the document with Azure Document Intelligence."
        )

    return result, operation_id


async def process_adi_2_ai_search(record: dict, chunk_by_page: bool = False) -> dict:
    """Process the extracted content from the Azure Document Intelligence service and prepare it for Azure Search.

    Args:
    -----
        record (dict): The record containing the extracted content.
        chunk_by_page (bool): Whether to chunk the content by page.

    Returns:
    --------
        dict: The processed content ready for Azure Search."""
    logging.info("Python HTTP trigger function processed a request.")

    storage_account_helper = await get_storage_account_helper()

    try:
        source = record["data"]["source"]
        logging.info(f"Request Body: {record}")
    except KeyError:
        return {
            "recordId": record["recordId"],
            "data": {},
            "errors": [
                {
                    "message": "Failed to extract data with ADI. Pass a valid source in the request body.",
                }
            ],
            "warnings": None,
        }
    else:
        logging.info(f"Source: {source}")

        try:
            source_parts = source.split("/")
            blob = "/".join(source_parts[4:])
            logging.info(f"Blob: {blob}")

            container = source_parts[3]

            container_and_blob = (container, blob)

            file_extension = blob.split(".")[-1]
            target_file_name = f"{record['recordId']}.{file_extension}"

            temp_file_path, _ = await storage_account_helper.download_blob_to_temp_dir(
                blob, container, target_file_name
            )
            logging.info(temp_file_path)
        except Exception as e:
            logging.error(f"Failed to download the blob: {e}")
            return {
                "recordId": record["recordId"],
                "data": {},
                "errors": [
                    {
                        "message": f"Failed to download the blob. Check the source and try again. {e}",
                    }
                ],
                "warnings": None,
            }

        try:
            result, operation_id = await analyse_document(temp_file_path)
        except Exception as e:
            logging.error(e)
            logging.info("Sleeping for 10 seconds and retrying")
            await asyncio.sleep(10)
            try:
                result, operation_id = await analyse_document(temp_file_path)
            except ValueError as inner_e:
                logging.error(inner_e)
                logging.error(
                    f"Failed to analyze the document with Azure Document Intelligence: {e}"
                )
                logging.error(
                    "Failed to analyse %s with Azure Document Intelligence.", blob
                )
                await storage_account_helper.add_metadata_to_blob(
                    blob, container, {"AzureSearch_Skip": "true"}
                )
                return {
                    "recordId": record["recordId"],
                    "data": {},
                    "errors": [
                        {
                            "message": f"Failed to analyze the document with Azure Document Intelligence. This blob will now be skipped {inner_e}",
                        }
                    ],
                    "warnings": None,
                }
            except Exception as inner_e:
                logging.error(inner_e)
                logging.error(
                    "Failed to analyse %s with Azure Document Intelligence.", blob
                )
                return {
                    "recordId": record["recordId"],
                    "data": {},
                    "errors": [
                        {
                            "message": f"Failed to analyze the document with Azure Document Intelligence. Check the logs and try again. {inner_e}",
                        }
                    ],
                    "warnings": None,
                }

        try:
            if chunk_by_page:
                cleaned_result = []
                markdown_content, page_numbers, page_offsets = create_page_wise_content(
                    result
                )
                content_with_figures_tasks = [
                    process_figures_from_extracted_content(
                        result,
                        operation_id,
                        container_and_blob,
                        page_content,
                        page_number=page_number,
                        page_offset=page_offset,
                    )
                    for page_content, page_number, page_offset in zip(
                        markdown_content, page_numbers, page_offsets
                    )
                ]
                content_with_figures = await asyncio.gather(*content_with_figures_tasks)

                with concurrent.futures.ProcessPoolExecutor() as executor:
                    futures = {
                        executor.submit(
                            build_and_clean_markdown_for_response,
                            extracted_page_content[0],
                            extracted_page_content[1],
                            page_number,
                            True,
                        ): extracted_page_content
                        for extracted_page_content, page_number in zip(
                            content_with_figures, page_numbers
                        )
                    }
                    for future in concurrent.futures.as_completed(futures):
                        cleaned_result.append(future.result())

            else:
                markdown_content = result.content

                (
                    extracted_content,
                    figures,
                ) = await process_figures_from_extracted_content(
                    result,
                    operation_id,
                    container_and_blob,
                    markdown_content,
                    page_offset=0,
                    page_number=None,
                )

                cleaned_result = build_and_clean_markdown_for_response(
                    extracted_content, figures, remove_irrelevant_figures=True
                )
        except Exception as e:
            logging.error(e)
            logging.error(f"Failed to process the extracted content: {e}")
            return {
                "recordId": record["recordId"],
                "data": {},
                "errors": [
                    {
                        "message": f"Failed to process the extracted content. Check the logs and try again. {e}",
                    }
                ],
                "warnings": None,
            }

        logging.info("Document Extracted")
        logging.info(f"Result: {cleaned_result}")

        src = {
            "recordId": record["recordId"],
            "data": {"extracted_content": cleaned_result},
        }

        json_str = json.dumps(src, indent=4)

        logging.info(f"final output: {json_str}")

        return src
