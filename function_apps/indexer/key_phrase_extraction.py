import logging
import json
import os
from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.core.exceptions import HttpResponseError
from azure.core.credentials import AzureKeyCredential
import asyncio

MAX_TEXT_ELEMENTS = 5120

def split_document(document, max_size):
    """Split a document into chunks of max_size."""
    return [document[i:i + max_size] for i in range(0, len(document), max_size)]

async def extract_key_phrases_from_text(data: list[str],max_key_phrase_count:int) -> list[str]:
    logging.info("Python HTTP trigger function processed a request.")

    max_retries = 5
    key_phrase_list = []
    text_analytics_client = TextAnalyticsClient(
            endpoint=os.environ["AIService__Services__Endpoint"],
            credential=AzureKeyCredential(os.environ["AIService__Services__Key"]),
        )

    try:
        async with text_analytics_client:
             retries = 0
             while retries < max_retries:
                try:
                     # Split large documents
                    split_documents = []
                    for doc in data:
                        if len(doc) > MAX_TEXT_ELEMENTS:
                            split_documents.extend(split_document(doc, MAX_TEXT_ELEMENTS))
                        else:
                            split_documents.append(doc)
                    result = await text_analytics_client.extract_key_phrases(split_documents)
                    for idx,doc in enumerate(result):
                        if not doc.is_error:
                            key_phrase_list.extend(doc.key_phrases[:max_key_phrase_count])
                        else:
                            raise Exception(f"Document {idx} error: {doc.error}")
                    break  # Exit the loop if the request is successful
                except HttpResponseError as e:
                    if e.status_code == 429:  # Rate limiting error
                        retries += 1
                        wait_time = 2 ** retries  # Exponential backoff
                        print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"An error occurred: {e}")
    except Exception as e:
        raise Exception(f"An error occurred: {e}")
    
    return key_phrase_list


async def process_key_phrase_extraction(record: dict,max_key_phrase_count:int =5 ) -> dict:
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
            [record["data"]["text"]],max_key_phrase_count
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
            ] = await extract_key_phrases_from_text([record["data"]["text"]],max_key_phrase_count)
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
