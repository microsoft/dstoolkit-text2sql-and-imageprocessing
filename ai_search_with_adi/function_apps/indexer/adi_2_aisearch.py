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
import aiohttp
import logging
from common.storage_account import StorageAccountHelper
import concurrent.futures
import json


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

    # Cropping the page. The rect requires the coordinates in the format (x0, y0, x1, y1).
    bbx = [x * 72 for x in bounding_box]
    rect = fitz.Rect(bbx)
    pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), clip=rect)

    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    doc.close()
    return img


def clean_adi_markdown(markdown_text: str, page_no:int,remove_irrelevant_figures=False):
    """Clean Markdown text extracted by the Azure Document Intelligence service.

    Args:
    -----
        markdown_text (str): The original Markdown text.
        remove_irrelevant_figures (bool): Whether to remove all figures or just irrelevant ones.

    Returns:
    --------
        str: The cleaned Markdown text.
    """

    # # Remove the page number comment
    # page_number_pattern = r"<!-- PageNumber=\"\d+\" -->"
    # cleaned_text = re.sub(page_number_pattern, "", markdown_text)

    # # Replace the page header comment with its content
    # page_header_pattern = r"<!-- PageHeader=\"(.*?)\" -->"
    # cleaned_text = re.sub(
    #     page_header_pattern, lambda match: match.group(1), cleaned_text
    # )

    # # Replace the page footer comment with its content
    # page_footer_pattern = r"<!-- PageFooter=\"(.*?)\" -->"
    # cleaned_text = re.sub(
    #     page_footer_pattern, lambda match: match.group(1), cleaned_text
    # )
    output_dict = {}
    comment_patterns = r"<!-- PageNumber=\"\d+\" -->|<!-- PageHeader=\".*?\" -->|<!-- PageFooter=\".*?\" -->"
    cleaned_text = re.sub(comment_patterns, "", markdown_text, flags=re.DOTALL)

    combined_pattern = r'(.*?)\n===|\n## ?(.*?)\n|\n### ?(.*?)\n'
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
    output_dict['content']  =  cleaned_text
    output_dict['section']  =  doc_metadata

    # add page number when chunk by page is enabled
    if page_no> -1:
        output_dict['page_number'] =  page_no

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


async def understand_image_with_vlm(image_base64):
    """
    Sends a base64-encoded image to a VLM (Vision Language Model) endpoint for financial analysis.

    Args:
        image_base64 (str): The base64-encoded string representation of the image.

    Returns:
        str: The response from the VLM, which is either a financial analysis or a statement indicating the image is not useful.
    """
    # prompt = "Describe the image ONLY IF it is useful for financial analysis. Otherwise, say 'NOT USEFUL IMAGE' and NOTHING ELSE. "
    prompt = "Perform financial analysis of the image ONLY IF the image is of graph, chart, flowchart or table. Otherwise, say 'NOT USEFUL IMAGE' and NOTHING ELSE. "
    headers = {"Content-Type": "application/json"}
    data = {"prompt": prompt, "image": image_base64}
    vlm_endpoint = os.environ["AIServices__VLM__Endpoint"]
    async with aiohttp.ClientSession() as session:
        async with session.post(
            vlm_endpoint, headers=headers, json=data, timeout=30
        ) as response:
            response_data = await response.json()
            response_text = response_data["response"].split("</s>")[0]

    if (
        "not useful for financial analysis" in response_text
        or "NOT USEFUL IMAGE" in response_text
    ):
        return "Irrelevant Image"
    else:
        return response_text


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

                image_base64 = pil_image_to_base64(cropped_image)

                img_description += await understand_image_with_vlm(image_base64)
                logging.info(f"\tDescription of figure {idx}: {img_description}")

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
    page_number = 0
    for page in result.pages:
        page_content = result.content[
            page.spans[0]["offset"] : page.spans[0]["offset"] + page.spans[0]["length"]
        ]
        page_wise_content.append(page_content)
        page_number+=1
        page_numbers.append(page_number)

    return page_wise_content,page_numbers


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
        # base64_encoded_file = base64.b64encode(file_read).decode("utf-8")

    async with DocumentIntelligenceClient(
        endpoint=os.environ["AIService__Services__Endpoint"],
        credential=AzureKeyCredential(os.environ["AIService__Services__Key"]),
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
                markdown_content,page_no = create_page_wise_content(result)
            else:
                markdown_content = result.content

            # Remove this line when VLM is ready
            content_with_figures = markdown_content

            # if chunk_by_page:
            #     tasks = [
            #         process_figures_from_extracted_content(
            #             temp_file_path, page_content, result.figures, page_number=idx
            #         )
            #         for idx, page_content in enumerate(markdown_content)
            #     ]
            #     content_with_figures = await asyncio.gather(*tasks)
            # else:
            #     content_with_figures = await process_figures_from_extracted_content(
            #         temp_file_path, markdown_content, result.figures
            #     )

            # Remove remove_irrelevant_figures=True when VLM is ready
            if chunk_by_page:
                cleaned_result = []
                with concurrent.futures.ProcessPoolExecutor() as executor:
                    results = executor.map(clean_adi_markdown,content_with_figures, page_no,[False] * len(content_with_figures))
                
                for cleaned_content in results:
                    cleaned_result.append(cleaned_content)
                    
                # with concurrent.futures.ProcessPoolExecutor() as executor:
                #     futures = {
                #         executor.submit(
                #             clean_adi_markdown, page_content, False
                #         ): page_content
                #         for page_content in content_with_figures
                #     }
                #     for future in concurrent.futures.as_completed(futures):
                #         cleaned_result.append(future.result())
            else:
                cleaned_result = clean_adi_markdown(
                    content_with_figures, page_no=-1,remove_irrelevant_figures=False
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

        return {
            "recordId": record["recordId"],
            "data": {"extracted_content": cleaned_result},
        }
