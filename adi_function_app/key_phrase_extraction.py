import logging
import json
import os
from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential
import asyncio

MAX_TEXT_ELEMENTS = 5120


def split_document(document, max_size):
    """Split a document into chunks of max_size and filter out any empty strings

    Args:
        document (str): The document to split.
        max_size (int): The maximum size of each chunk.

    Returns:
        list: The list of document chunks."""
    return [
        document[i : i + max_size]
        for i in range(0, len(document), max_size)
        if len(document[i : i + max_size]) > 0
    ]


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def extract_key_phrases_from_batch(
    batch_data: list[str], max_key_phrase_count: int
) -> list[str]:
    """Extract key phrases from text using Azure AI services.

    Args:
        batch_data (list[str]): The list of text to process.
        max_key_phrase_count(int): no of keywords to return

    Returns:
        list: The list of key phrases."""

    key_phrase_list = []

    text_analytics_client = TextAnalyticsClient(
        endpoint=os.environ["AIService__Services__Endpoint"],
        credential=DefaultAzureCredential(
            managed_identity_client_id=os.environ.get("FunctionApp__ClientId")
        ),
    )

    async with text_analytics_client:
        try:
            result = await text_analytics_client.extract_key_phrases(batch_data)
            for doc in result:
                if not doc.is_error:
                    key_phrase_list.extend(doc.key_phrases[:max_key_phrase_count])
                else:
                    raise Exception(f"Document error: {doc.error}")
        except HttpResponseError as e:
            logging.error("An error occurred: %s", e)
            raise e

    return key_phrase_list


async def extract_key_phrases_from_text(
    data: list[str], max_key_phrase_count: int
) -> list[str]:
    """Extract key phrases from text using Azure AI services.

    Args:
        data (list[str]): The list of text to process.
        max_key_phrase_count(int): no of keywords to return"""
    logging.info("Python HTTP trigger function processed a request.")
    key_phrase_list = []

    split_documents = []
    for doc in data:
        if len(doc) > MAX_TEXT_ELEMENTS:
            split_documents.extend(split_document(doc, MAX_TEXT_ELEMENTS))
        elif len(doc) > 0:
            split_documents.append(doc)

    # Filter out any empty documents
    split_documents = [doc for doc in split_documents if len(doc) > 0]

    for i in range(0, len(split_documents), 10):
        key_phrase_list.extend(
            await extract_key_phrases_from_batch(
                split_documents[i : i + 10], max_key_phrase_count
            )
        )

        if len(key_phrase_list) > max_key_phrase_count:
            key_phrase_list = key_phrase_list[:max_key_phrase_count]
            break

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
        extracted_record["data"]["keyPhrases"] = await extract_key_phrases_from_text(
            [record["data"]["text"]], max_key_phrase_count
        )
    except Exception as e:
        logging.error("key phrase extraction Error: %s", e)
        await asyncio.sleep(10)
        try:
            extracted_record = {
                "recordId": record["recordId"],
                "data": {},
                "errors": None,
                "warnings": None,
            }
            extracted_record["data"][
                "keyPhrases"
            ] = await extract_key_phrases_from_text(
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
    json_str = json.dumps(extracted_record, indent=4)

    logging.info(f"key phrase extraction output: {json_str}")
    return extracted_record
