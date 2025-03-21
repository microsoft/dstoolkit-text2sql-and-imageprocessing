# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import os
import urllib
import tempfile
from azure.storage.blob.aio import BlobServiceClient
from azure.identity import DefaultAzureCredential
import base64
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    DocumentContentFormat,
    AnalyzeOutputOption,
    AnalyzeDocumentRequest,
)
import asyncio
from typing import Union
from tenacity import retry, stop_after_attempt, wait_exponential
from layout_holders import (
    FigureHolder,
    LayoutHolder,
    PageWiseContentHolder,
    NonPageWiseContentHolder,
    PageNumberTrackingHolder,
)
import re


class StorageAccountHelper:
    """Helper class for interacting with Azure Blob Storage."""

    @property
    def account_url(self) -> str:
        """Get the account URL of the Azure Blob Storage."""
        storage_account_name = os.environ["StorageAccount__Name"]
        return f"https://{storage_account_name}.blob.core.windows.net"

    async def get_client(self):
        """Get the BlobServiceClient object."""

        credential = DefaultAzureCredential()
        return BlobServiceClient(account_url=self.account_url, credential=credential)

    async def add_metadata_to_blob(
        self, source: str, container: str, metadata: dict, upsert: bool = False
    ) -> None:
        """Add metadata to the blob.

        Args
            source (str): The source of the blob.
            container (str): The container of the blob.
            metadata (dict): The metadata to add to the blob."""

        logging.info("Adding Metadata")

        blob = urllib.parse.unquote(source, encoding="utf-8")

        blob_service_client = await self.get_client()
        async with blob_service_client:
            async with blob_service_client.get_blob_client(
                container=container, blob=blob
            ) as blob_client:
                blob_properties = await blob_client.get_blob_properties()

                if upsert:
                    updated_metadata = blob_properties.metadata
                    updated_metadata.update(metadata)
                else:
                    updated_metadata = metadata

                await blob_client.set_blob_metadata(updated_metadata)

        logging.info("Metadata Added")

    async def upload_blob(
        self, container: str, blob: str, data, content_type: str
    ) -> str:
        """Upload the file to the Azure Blob Storage.

        Args:
            container (str): The container of the blob.
            blob (str): The blob name.
            data (bytes): The data to upload.

        Returns:
            str: url of the uploaded blob."""

        logging.info("Uploading Blob...")
        logging.info(f"Container: {container}")
        logging.info(f"Blob: {blob}")

        blob_service_client = await self.get_client()
        async with blob_service_client:
            async with blob_service_client.get_blob_client(
                container=container, blob=blob
            ) as blob_client:
                await blob_client.upload_blob(
                    data,
                    overwrite=True,
                    blob_type="BlockBlob",
                    content_type=content_type,
                )

        return blob_client.url

    async def download_blob_to_temp_dir(
        self, source: str, container: str, target_file_name
    ) -> tuple[str, dict]:
        """Download the file from the Azure Blob Storage.

        Args:
            source (str): The source of the blob.
            container (str): The container of the blob.
            target_file_name (str): The target file name."""

        blob = urllib.parse.unquote(source)

        blob_service_client = await self.get_client()
        async with blob_service_client:
            async with blob_service_client.get_blob_client(
                container=container, blob=blob
            ) as blob_client:
                blob_download = await blob_client.download_blob()
                blob_contents = await blob_download.readall()

                blob_properties = await blob_client.get_blob_properties()

        logging.info("Blob Downloaded")
        # Get the temporary directory
        temp_dir = tempfile.gettempdir()

        # Define the temporary file path
        temp_file_path = os.path.join(temp_dir, target_file_name)

        # Write the blob contents to the temporary file
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(blob_contents)

        return temp_file_path, blob_properties.metadata


class LayoutAnalysis:
    def __init__(
        self,
        page_wise: bool = False,
        extract_figures: bool = True,
        record_id: int = None,
        source: str = None,
    ):
        self.result = None
        self.operation_id = None

        self.page_wise = page_wise
        self.extract_figures = extract_figures

        self.record_id = record_id
        self.source = source

        self.blob = None
        self.container = None
        self.file_extension = None
        self.target_file_name = None

    def extract_file_info(self):
        """Extract the file information from the source."""
        source_parts = self.source.split("/")
        self.blob = "/".join(source_parts[4:])
        logging.info(f"Blob: {self.blob}")

        self.container = source_parts[3]

        self.images_container = f"{self.container}-figures"

        self.file_extension = self.blob.split(".")[-1]

        self.target_file_name = f"{self.record_id}.{self.file_extension}"

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def download_figure_image(self, figure_id: str) -> bytearray:
        """Download the image associated with a figure extracted by the Azure Document Intelligence service.

        Args:
        -----
            model_id (str): The model ID used for the analysis.
            operation_id (str): The operation ID of the analysis.
            figure_id (str): The ID of the figure to download.

        Returns:
        --------
            bytes: The image associated with the figure."""

        logging.info(f"Downloading Image for Figure ID: {figure_id}")
        document_intelligence_client = await self.get_document_intelligence_client()
        try:
            async with document_intelligence_client:
                response = await document_intelligence_client.get_analyze_result_figure(
                    model_id=self.result.model_id,
                    result_id=self.operation_id,
                    figure_id=figure_id,
                )

                logging.info(f"Response: {response}")

                full_bytes = bytearray()
                async for chunk in response:
                    full_bytes.extend(chunk)
        except Exception as e:
            logging.error(e)
            logging.error(f"Failed to download image for Figure ID: {figure_id}")
            raise e

        return full_bytes

    async def process_figures_from_extracted_content(
        self,
        text_holder: LayoutHolder,
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
        figure_upload_tasks = []

        storage_account_helper = await self.get_storage_account_helper()
        if self.result.figures:
            for figure in self.result.figures:
                if figure.id is None:
                    continue

                for region in figure.bounding_regions:
                    if (
                        text_holder.page_number is not None
                        and region.page_number != text_holder.page_number
                    ):
                        continue

                    logging.info(f"Figure ID: {figure.id}")
                    download_image_tasks.append(
                        self.download_figure_image(
                            figure_id=figure.id,
                        )
                    )

                    blob = f"{self.blob}/{figure.id}.png"

                    caption = (
                        figure.caption.content if figure.caption is not None else None
                    )

                    logging.info(f"Figure Caption: {caption}")

                    uri = f"""{
                        storage_account_helper.account_url}/{self.images_container}/{blob}"""

                    offset = figure.spans[0].offset - text_holder.page_offsets

                    image_processing_data = FigureHolder(
                        figure_id=figure.id,
                        container=self.images_container,
                        blob=blob,
                        caption=caption,
                        offset=offset,
                        length=figure.spans[0].length,
                        page_number=region.page_number,
                        uri=uri,
                    )

                    figure_processing_datas.append(image_processing_data)

                    break

        logging.info("Running image download tasks")
        image_responses = await asyncio.gather(*download_image_tasks)
        logging.info("Finished image download tasks")

        for figure_processing_data, response in zip(
            figure_processing_datas, image_responses
        ):
            base_64_image = base64.b64encode(response).decode("utf-8")

            image_data = base64.b64decode(base_64_image)

            figure_processing_data.data = base_64_image

            figure_upload_tasks.append(
                storage_account_helper.upload_blob(
                    figure_processing_data.container,
                    figure_processing_data.blob,
                    image_data,
                    "image/png",
                )
            )

            text_holder.figures.append(figure_processing_data)

        await asyncio.gather(*figure_upload_tasks)

    def create_page_wise_content(self) -> list[LayoutHolder]:
        """Create a list of page-wise content extracted by the Azure Document Intelligence service.

        Args:
        -----
            result (AnalyzeResult): The result of the document analysis.

        Returns:
        --------
            list: A list of page-wise content extracted by the Azure Document Intelligence service.
        """

        page_wise_contents = []

        for page in self.result.pages:
            page_content = self.result.content[
                page.spans[0]["offset"] : page.spans[0]["offset"]
                + page.spans[0]["length"]
            ]

            page_wise_contents.append(
                LayoutHolder(
                    content=page_content,
                    page_number=page.page_number,
                    page_offsets=page.spans[0]["offset"],
                )
            )

        return page_wise_contents

    def create_page_number_tracking_holder(self) -> list[PageNumberTrackingHolder]:
        """Create a list of the starting sentence of each page so we can assign the starting sentence to the page number.

        Returns:
        --------
            list: A list of the starting sentence of each page."""

        page_number_tracking_holders = []

        for page in self.result.pages:
            page_content = self.result.content[
                page.spans[0]["offset"] : page.spans[0]["offset"]
                + page.spans[0]["length"]
            ]

            # Remove any leading whitespace/newlines.
            cleaned_content = page_content.lstrip()
            # Strip the html comment but keep the content
            html_comments_pattern = re.compile(r"<!--.*?-->", re.DOTALL)
            cleaned_content = html_comments_pattern.sub("", cleaned_content)

            # Remove anything inside a figure tag
            cleaned_content = re.sub(
                "<figure>(.*?)</figure>",
                "",
                cleaned_content,
                flags=re.DOTALL | re.MULTILINE,
            )
            logging.info(f"Page Number: {page.page_number}")
            logging.info(f"Content for Page Detection: {page_content}")
            logging.info(f"Cleaned Content for Page Detection: {cleaned_content}")

            if len(cleaned_content) == 0:
                logging.error(
                    "No content found in the cleaned result for page %s.",
                    page.page_number,
                )
                cleaned_content = None
            else:
                cleaned_content = cleaned_content.strip()

            page_number_tracking_holders.append(
                PageNumberTrackingHolder(
                    page_number=page.page_number,
                    page_content=cleaned_content,
                )
            )

        return page_number_tracking_holders

    async def get_document_intelligence_client(self) -> DocumentIntelligenceClient:
        """Get the Azure Document Intelligence client.

        Returns:
        --------
            DocumentIntelligenceClient: The Azure Document Intelligence client."""

        credential = DefaultAzureCredential()

        return DocumentIntelligenceClient(
            endpoint=os.environ["AIService__DocumentIntelligence__Endpoint"],
            credential=credential,
        )

    async def get_storage_account_helper(self) -> StorageAccountHelper:
        """Get the Storage Account Helper.

        Returns:
        --------
            StorageAccountHelper: The Storage Account Helper."""

        return StorageAccountHelper()

    @retry(
        stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def analyse_document(self, file_path: str):
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

        document_intelligence_client = await self.get_document_intelligence_client()
        async with document_intelligence_client:
            poller = await document_intelligence_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(bytes_source=file_read),
                output_content_format=DocumentContentFormat.MARKDOWN,
                output=[AnalyzeOutputOption.FIGURES],
            )

            self.result = await poller.result()

            self.operation_id = poller.details["operation_id"]

        if (
            self.result is None
            or self.result.content is None
            or self.result.pages is None
        ):
            raise ValueError(
                "Failed to analyze the document with Azure Document Intelligence."
            )

    async def analyse(self):
        """Orchestrate the analysis of the document using the Azure Document Intelligence service.

        Args:
        -----
            record_id (int): The record ID.
            source (str): The source of the document to analyse."""
        try:
            self.extract_file_info()
            storage_account_helper = await self.get_storage_account_helper()
            temp_file_path, _ = await storage_account_helper.download_blob_to_temp_dir(
                self.blob, self.container, self.target_file_name
            )
            logging.info(temp_file_path)
        except Exception as e:
            logging.error(f"Failed to download the blob: {e}")
            return {
                "recordId": self.record_id,
                "data": None,
                "errors": [
                    {
                        "message": f"Failed to download the blob. Check the source and try again. {e}",
                    }
                ],
                "warnings": None,
            }

        try:
            await self.analyse_document(temp_file_path)
        except Exception as e:
            logging.error(e)
            logging.error(
                "Failed to analyse %s with Azure Document Intelligence.", self.blob
            )
            await storage_account_helper.add_metadata_to_blob(
                self.blob, self.container, {"AzureSearch_Skip": "true"}, upsert=True
            )
            return {
                "recordId": self.record_id,
                "data": None,
                "errors": [
                    {
                        "message": f"Failed to analyze the document with Azure Document Intelligence. Check the logs and try again. {e}",
                    }
                ],
                "warnings": None,
            }

        try:
            if self.page_wise:
                cleaned_text_holders = []
                page_wise_text_holders = self.create_page_wise_content()
                content_with_figures_tasks = []

                for page_wise_text_holder in page_wise_text_holders:
                    if self.extract_figures:
                        content_with_figures_tasks.append(
                            self.process_figures_from_extracted_content(
                                page_wise_text_holder
                            )
                        )

                    if len(page_wise_text_holder.content) == 0:
                        logging.error(
                            "No content found in the cleaned result for slide %s.",
                            page_wise_text_holder.page_number,
                        )
                    else:
                        cleaned_text_holders.append(page_wise_text_holder)

                if self.extract_figures:
                    await asyncio.gather(*content_with_figures_tasks)

                output_record = PageWiseContentHolder(
                    page_wise_layout=cleaned_text_holders
                )
            else:
                text_content = LayoutHolder(
                    content=self.result.content, page_number=None, page_offsets=0
                )

                if self.extract_figures:
                    await self.process_figures_from_extracted_content(text_content)

                page_number_tracking_holders = self.create_page_number_tracking_holder()

                output_record = NonPageWiseContentHolder(
                    layout=text_content,
                    page_number_tracking_holders=page_number_tracking_holders,
                )

        except Exception as e:
            logging.error(e)
            logging.error(f"Failed to process the extracted content: {e}")
            return {
                "recordId": self.record_id,
                "data": None,
                "errors": [
                    {
                        "message": f"Failed to process the extracted content. Check the logs and try again. {e}",
                    }
                ],
                "warnings": None,
            }

        output_holder = {
            "recordId": self.record_id,
            "data": output_record.model_dump(),
            "errors": None,
            "warnings": None,
        }

        logging.info(f"final output: {output_holder}")

        return output_holder


async def process_layout_analysis(
    record: dict, page_wise: bool = False, extract_figures: bool = True
) -> dict:
    """Process the extracted content from the Azure Document Intelligence service and prepare it for Azure Search.

    Args:
    -----
        record (dict): The record containing the extracted content.
        page_wise (bool): Whether to chunk the content by page.

    Returns:
    --------
        dict: The processed content ready for Azure Search."""
    logging.info("Python HTTP trigger function processed a request.")

    try:
        source = record["data"]["source"]
        record_id = record["recordId"]
        logging.info(f"Request Body: {record}")

        layout_analysis = LayoutAnalysis(
            page_wise=page_wise,
            extract_figures=extract_figures,
            record_id=record_id,
            source=source,
        )

        return await layout_analysis.analyse()
    except KeyError:
        return {
            "recordId": record["recordId"],
            "data": None,
            "errors": [
                {
                    "message": "Failed to extract data with ADI. Pass a valid source in the request body.",
                }
            ],
            "warnings": None,
        }
