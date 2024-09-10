# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import base64
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult, ContentFormat
import os
import re
import asyncio
import fitz
from PIL import Image
import io
import logging
from storage_account import StorageAccountHelper
import concurrent.futures
import json
from openai import AsyncAzureOpenAI
import openai
from environment import IdentityType, get_identity_type


def crop_image_from_pdf_page(pdf_path, page_number, bounding_box):
    """
    Crops a region from a given page in a PDF and returns it as an image.

    :param pdf_path: Path to the PDF file.
    :param page_number: The page number to crop from (0-indexed).
    :param bounding_box: A tuple of (x0, y0, x1, y1) coordinates for the bounding box.
    :return: A PIL Image of the cropped area.
    """
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number)

    logging.debug(f"Bounding Box: {bounding_box}")
    logging.debug(f"Page Number: {page_number}")

    # Cropping the page. The rect requires the coordinates in the format (x0, y0, x1, y1).
    bbx = [x * 72 for x in bounding_box]
    rect = fitz.Rect(bbx)
    pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), clip=rect)

    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    if pix.width == 0 or pix.height == 0:
        logging.error("Cropped image has 0 width or height.")
        return None

    doc.close()
    return img


def clean_adi_markdown(
    markdown_text: str, page_no: int = None, remove_irrelevant_figures=False
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
    comment_patterns = r"<!-- PageNumber=\"\d+\" -->|<!-- PageHeader=\".*?\" -->|<!-- PageFooter=\".*?\" -->|<!-- PageBreak -->"
    cleaned_text = re.sub(comment_patterns, "", markdown_text, flags=re.DOTALL)

    combined_pattern = r"(.*?)\n===|\n#+\s*(.*?)\n"
    doc_metadata = re.findall(combined_pattern, cleaned_text, re.DOTALL)
    doc_metadata = [match for group in doc_metadata for match in group if match]

    if remove_irrelevant_figures:
        # Remove irrelevant figures
        irrelevant_figure_pattern = (
            r"<figure>.*?<!-- FigureContent=\"Irrelevant Image\" -->.*?</figure>\s*"
        )
        cleaned_text = re.sub(
            irrelevant_figure_pattern, "", cleaned_text, flags=re.DOTALL
        )

    # Replace ':selected:' with a new line
    cleaned_text = re.sub(r":(selected|unselected):", "\n", cleaned_text)
    output_dict["content"] = cleaned_text
    output_dict["sections"] = doc_metadata

    # add page number when chunk by page is enabled
    if page_no is not None:
        output_dict["page_number"] = page_no

    return output_dict


def update_figure_description(md_content, img_description, idx):
    """
    Updates the figure description in the Markdown content.

    Args:
        md_content (str): The original Markdown content.
        img_description (str): The new description for the image.
        idx (int): The index of the figure.

    Returns:
        str: The updated Markdown content with the new figure description.
    """

    # The substring you're looking for
    start_substring = f"![](figures/{idx})"
    end_substring = "</figure>"
    new_string = f'<!-- FigureContent="{img_description}" -->'

    new_md_content = md_content
    # Find the start and end indices of the part to replace
    start_index = md_content.find(start_substring)
    if start_index != -1:  # if start_substring is found
        start_index += len(
            start_substring
        )  # move the index to the end of start_substring
        end_index = md_content.find(end_substring, start_index)
        if end_index != -1:  # if end_substring is found
            # Replace the old string with the new string
            new_md_content = (
                md_content[:start_index] + new_string + md_content[end_index:]
            )

    return new_md_content


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
    api_version = os.environ.get("OpenAI__ApiVersion")
    model = os.environ.get("OpenAI__MultiModalDeployment")

    if get_identity_type() != IdentityType.SYSTEM_ASSIGNED:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        api_key = None
    elif get_identity_type() != IdentityType.USER_ASSIGNED:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(
                managed_identity_client_id=os.environ.get("FunctionApp__ClientId")
            ),
            "https://cognitiveservices.azure.com/.default",
        )
        api_key = None
    else:
        token_provider = None
        api_key = os.environ.get("OpenAI__ApiKey")

    system_prompt = """You are an expert in image analysis. Use your experience and skills to provided a detailed description of any provided images. You should FOCUS on what info can be inferred from the image and the meaning of the data inside the image. Draw actionable insights and conclusions from the image.

    If the image is a chart for instance, you should describe the data trends, patterns, and insights that can be drawn from the chart.

    If the image is a map, you should describe the geographical features, landmarks, and any other relevant information that can be inferred from the map.

    If the image is a diagram, you should describe the components, relationships, and any other relevant information that can be inferred from the diagram.

    Include any data points, labels, and other relevant information that can be inferred from the image.

    IMPORTANT: If the provided image is a logo or photograph, simply return 'Irrelevant Image'."""

    user_input = "Describe this image with technical analysis. Provide a well-structured, description."

    if caption != "":
        user_input += f" (note: it has image caption: {caption})"

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

        raise Exception("OpenAI Rate Limit Error: No retries left.") from e


def pil_image_to_base64(image, image_format="JPEG"):
    """
    Converts a PIL image to a base64-encoded string.

    Args:
        image (PIL.Image.Image): The image to be converted.
        image_format (str): The format to save the image in. Defaults to "JPEG".

    Returns:
        str: The base64-encoded string representation of the image.
    """
    if image.mode == "RGBA" and image_format == "JPEG":
        image = image.convert("RGB")
    buffered = io.BytesIO()
    image.save(buffered, format=image_format)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


async def mark_image_as_irrelevant():
    return "Irrelevant Image"


async def process_figures_from_extracted_content(
    file_path: str, markdown_content: str, figures: list, page_number: None | int = None
) -> str:
    """Process the figures extracted from the content using ADI and send them for analysis.

    Args:
    -----
        file_path (str): The path to the PDF file.
        markdown_content (str): The extracted content in Markdown format.
        figures (list): The list of figures extracted by the Azure Document Intelligence service.
        page_number (int): The page number to process. If None, all pages are processed.

    Returns:
    --------
        str: The updated Markdown content with the figure descriptions."""

    image_understanding_tasks = []
    for idx, figure in enumerate(figures):
        img_description = ""
        logging.debug(f"Figure #{idx} has the following spans: {figure.spans}")

        caption_region = figure.caption.bounding_regions if figure.caption else []
        for region in figure.bounding_regions:
            # Skip the region if it is not on the specified page
            if page_number is not None and region.page_number != page_number:
                continue

            if region not in caption_region:
                # To learn more about bounding regions, see https://aka.ms/bounding-region
                bounding_box = (
                    region.polygon[0],  # x0 (left)
                    region.polygon[1],  # y0 (top)
                    region.polygon[4],  # x1 (right)
                    region.polygon[5],  # y1 (bottom)
                )
                cropped_image = crop_image_from_pdf_page(
                    file_path, region.page_number - 1, bounding_box
                )  # page_number is 1-indexed3

                if cropped_image is None:
                    image_understanding_tasks.append(mark_image_as_irrelevant())
                else:
                    image_base64 = pil_image_to_base64(cropped_image)

                    image_understanding_tasks.append(
                        understand_image_with_gptv(image_base64, figure.caption.content)
                    )
                    logging.info(f"\tDescription of figure {idx}: {img_description}")
                    break

    image_descriptions = await asyncio.gather(*image_understanding_tasks)

    for idx, img_description in enumerate(image_descriptions):
        markdown_content = update_figure_description(
            markdown_content, img_description, idx
        )

    return markdown_content


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

    for page_number, page in enumerate(result.pages):
        page_content = result.content[
            page.spans[0]["offset"] : page.spans[0]["offset"] + page.spans[0]["length"]
        ]
        page_wise_content.append(page_content)
        page_numbers.append(page_number)

    return page_wise_content, page_numbers


async def analyse_document(file_path: str) -> AnalyzeResult:
    """Analyse a document using the Azure Document Intelligence service.

    Args:
    -----
        file_path (str): The path to the document to analyse.

    Returns:
    --------
        AnalyzeResult: The result of the document analysis."""
    with open(file_path, "rb") as f:
        file_read = f.read()

    if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
        credential = DefaultAzureCredential()
    elif get_identity_type() == IdentityType.USER_ASSIGNED:
        credential = DefaultAzureCredential(
            managed_identity_client_id=os.environ["FunctionApp__ClientId"]
        )
    else:
        credential = AzureKeyCredential(os.environ["AIService__Services__Key"])

    async with DocumentIntelligenceClient(
        endpoint=os.environ["AIService__Services__Endpoint"],
        credential=credential,
    ) as document_intelligence_client:
        poller = await document_intelligence_client.begin_analyze_document(
            model_id="prebuilt-layout",
            analyze_request=file_read,
            output_content_format=ContentFormat.MARKDOWN,
            content_type="application/octet-stream",
        )

        result = await poller.result()

    if result is None or result.content is None or result.pages is None:
        raise ValueError(
            "Failed to analyze the document with Azure Document Intelligence."
        )

    return result


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

    storage_account_helper = StorageAccountHelper()

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
            result = await analyse_document(temp_file_path)
        except Exception as e:
            logging.error(e)
            logging.info("Sleeping for 10 seconds and retrying")
            await asyncio.sleep(10)
            try:
                result = await analyse_document(temp_file_path)
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
                markdown_content, page_numbers = create_page_wise_content(result)
                content_with_figures_tasks = [
                    process_figures_from_extracted_content(
                        temp_file_path,
                        page_content,
                        result.figures,
                        page_number=page_number,
                    )
                    for page_content, page_number in zip(markdown_content, page_numbers)
                ]
                content_with_figures = await asyncio.gather(*content_with_figures_tasks)

                with concurrent.futures.ProcessPoolExecutor() as executor:
                    futures = {
                        executor.submit(
                            clean_adi_markdown, page_content, page_number, False
                        ): page_content
                        for page_content, page_number in zip(
                            content_with_figures, page_numbers
                        )
                    }
                    for future in concurrent.futures.as_completed(futures):
                        cleaned_result.append(future.result())

            else:
                markdown_content = result.content
                content_with_figures = await process_figures_from_extracted_content(
                    temp_file_path, markdown_content, result.figures
                )
                cleaned_result = clean_adi_markdown(
                    content_with_figures, remove_irrelevant_figures=False
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
