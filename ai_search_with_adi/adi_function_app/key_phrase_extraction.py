# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import json
import os
from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.core.exceptions import HttpResponseError
from azure.core.credentials import AzureKeyCredential
import asyncio
from azure.identity import DefaultAzureCredential
from environment import IdentityType, get_identity_type

MAX_TEXT_ELEMENTS = 5120


def split_document(document: str, max_size: int) -> list[str]:
    """Split a document into chunks of max_size.

    Args:
        document (str): The document to split.
        max_size (int): The maximum size of each chunk."""
    return [document[i : i + max_size] for i in range(0, len(document), max_size)]


async def extract_key_phrases_from_text(
    data: list[str], max_key_phrase_count: int, retries_left: int = 3
) -> list[str]:
    """Extract key phrases from the text.

    Args:
        data (list[str]): The text data.
        max_key_phrase_count (int): The maximum number of key phrases to return.

    Returns:
        list[str]: The key phrases extracted from the text."""
    logging.info("Python HTTP trigger function processed a request.")

    key_phrase_list = []

    if get_identity_type() == IdentityType.SYSTEM_ASSIGNED:
        credential = DefaultAzureCredential()
    elif get_identity_type() == IdentityType.USER_ASSIGNED:
        credential = DefaultAzureCredential(
            managed_identity_client_id=os.environ.get("FunctionApp__ClientId")
        )
    else:
        credential = AzureKeyCredential(os.environ.get("AIService__Services__Key"))
    text_analytics_client = TextAnalyticsClient(
        endpoint=os.environ.get("AIService__Services__Endpoint"),
        credential=credential,
    )

    async with text_analytics_client:
        try:
            # Split large documents
            split_documents = []
            for doc in data:
                if len(doc) > MAX_TEXT_ELEMENTS:
                    split_documents.extend(split_document(doc, MAX_TEXT_ELEMENTS))
                else:
                    split_documents.append(doc)

            result = await text_analytics_client.extract_key_phrases(split_documents)
            for idx, doc in enumerate(result):
                if not doc.is_error:
                    key_phrase_list.extend(doc.key_phrases[:max_key_phrase_count])
                else:
                    raise Exception(f"Document {idx} error: {doc.error}")
        except HttpResponseError as e:
            if e.status_code == 429 and retries_left > 0:  # Rate limiting error
                wait_time = 2**retries_left  # Exponential backoff
                logging.info(
                    "%s Rate limit exceeded. Retrying in %s seconds...", e, wait_time
                )
                await asyncio.sleep(wait_time)
                return await extract_key_phrases_from_text(
                    data, max_key_phrase_count, retries_left - 1
                )
            else:
                raise Exception(f"An error occurred: {e}") from e

    return key_phrase_list


async def process_key_phrase_extraction(
    record: dict, max_key_phrase_count: int = 5
) -> dict:
    """Extract key phrases using azure ai services.

    Args:
        record (dict): The record to process.
        max_key_phrase_count(int): no of keywords to return

    Returns:
        dict: extracted key words."""

    try:
        json_str = json.dumps(record, indent=4)

        logging.info(f"key phrase extraction Input: {json_str}")
        extracted_record = {
            "recordId": record["recordId"],
            "data": {},
            "errors": None,
            "warnings": None,
        }
        extracted_record["data"]["key_phrases"] = await extract_key_phrases_from_text(
            [record["data"]["text"]], max_key_phrase_count
        )
    except Exception as inner_e:
        logging.error("key phrase extraction Error: %s", inner_e)
        logging.error(
            "Failed to extract key phrase. Check function app logs for more details of exact failure."
        )
        return {
            "recordId": record["recordId"],
            "data": {},
            "errors": [
                {
                    "message": "Failed to extract key phrase. Check function app logs for more details of exact failure."
                }
            ],
            "warnings": None,
        }
    else:
        json_str = json.dumps(extracted_record, indent=4)

        logging.info(f"key phrase extraction output: {json_str}")
        return extracted_record
