# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import os
import tempfile
from azure.storage.blob.aio import BlobServiceClient
from azure.identity import DefaultAzureCredential
import urllib


class StorageAccountHelper:
    def __init__(self) -> None:
        self._client_id = os.environ["FunctionApp__ClientId"]

        self._endpoint = os.environ["StorageAccount__Endpoint"]

    async def get_client(self):
        credential = DefaultAzureCredential(managed_identity_client_id=self._client_id)

        return BlobServiceClient(account_url=self._endpoint, credential=credential)

    async def add_metadata_to_blob(self, source: str, container: str, metadata) -> None:
        """Add metadata to the business glossary blob."""

        blob = urllib.parse.unquote_plus(source)

        blob_service_client = await self.get_client()
        async with blob_service_client:
            async with blob_service_client.get_blob_client(
                container=container, blob=blob
            ) as blob_client:
                await blob_client.set_blob_metadata(metadata)

        logging.info("Metadata Added")

    async def download_blob_to_temp_dir(
        self, source: str, container: str, target_file_name
    ) -> tuple[str, dict]:
        """Download the business glossary file from the Azure Blob Storage."""

        blob = urllib.parse.unquote_plus(source)

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

    async def upload_business_glossary_dataframe(self, df: str, sheet: str) -> str:
        """Upload the business glossary dataframe to a JSONL file."""
        json_lines = df.to_json(orient="records", lines=True)

        container = os.environ["StorageAccount__BusinessGlossary__Container"]
        blob = f"{sheet}.jsonl"
        blob_service_client = await self.get_client()
        async with blob_service_client:
            async with blob_service_client.get_blob_client(
                container=container, blob=blob
            ) as blob_client:
                await blob_client.upload_blob(json_lines, overwrite=True)
