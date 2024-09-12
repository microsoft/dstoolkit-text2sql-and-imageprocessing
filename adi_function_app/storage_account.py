# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import os
import tempfile
from azure.storage.blob.aio import BlobServiceClient
from azure.identity import DefaultAzureCredential
import urllib
from environment import IdentityType, get_identity_type


class StorageAccountHelper:
    """Helper class for interacting with Azure Blob Storage."""

    async def get_client(self):
        """Get the BlobServiceClient object."""
        if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
            endpoint = os.environ.get("StorageAccount__Endpoint")
            credential = DefaultAzureCredential()
            return BlobServiceClient(account_url=endpoint, credential=credential)
        elif get_identity_type() == IdentityType.USER_ASSIGNED:
            endpoint = os.environ.get("StorageAccount__Endpoint")
            credential = DefaultAzureCredential(
                managed_identity_client_id=os.environ.get("FunctionApp__ClientId")
            )
            return BlobServiceClient(account_url=endpoint, credential=credential)
        else:
            endpoint = os.environ.get("StorageAccount__ConnectionString")
            return BlobServiceClient(account_url=endpoint)

    async def add_metadata_to_blob(
        self, source: str, container: str, metadata: dict
    ) -> None:
        """Add metadata to the blob.

        Args
            source (str): The source of the blob.
            container (str): The container of the blob.
            metadata (dict): The metadata to add to the blob."""

        blob = urllib.parse.unquote_plus(source)

        blob_service_client = await self.get_client()
        async with blob_service_client:
            async with blob_service_client.get_blob_client(
                container=container, blob=blob
            ) as blob_client:
                await blob_client.set_blob_metadata(metadata)

        logging.info("Metadata Added")

    async def upload_blob(
        self, container: str, blob: str, data, content_type: str
    ) -> str:
        """Upload the file to the Azure Blob Storage.

        Args:
            container (str): The container of the blob.
            blob (str): The blob name.
            data (bytes): The data to upload."""

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

    async def download_blob_to_temp_dir(
        self, source: str, container: str, target_file_name
    ) -> tuple[str, dict]:
        """Download the file from the Azure Blob Storage.

        Args:
            source (str): The source of the blob.
            container (str): The container of the blob.
            target_file_name (str): The target file name."""

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
