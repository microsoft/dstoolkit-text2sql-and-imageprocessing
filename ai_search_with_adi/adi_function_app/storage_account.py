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

    def __init__(self) -> None:
        """Initialize the StorageAccountHelper class."""
        self._endpoint = os.environ["StorageAccount__ConnectionString"]

    async def get_client(self):
        """Get the BlobServiceClient object."""
        if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
            credential = DefaultAzureCredential()
            return BlobServiceClient(account_url=self._endpoint, credential=credential)
        elif get_identity_type() == IdentityType.USER_ASSIGNED:
            credential = DefaultAzureCredential(
                managed_identity_client_id=os.environ["FunctionApp__ClientId"]
            )
            return BlobServiceClient(account_url=self._endpoint, credential=credential)
        else:
            return BlobServiceClient(account_url=self._endpoint)

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
