# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import datetime, timedelta, timezone
import azure.functions as func
import logging
import json
import asyncio

from adi_2_ai_search import process_adi_2_ai_search
from common.service_bus import ServiceBusHelper
from pre_embedding_cleaner import process_pre_embedding_cleaner

from text_split import process_text_split
from ai_search_2_compass import process_ai_search_2_compass
from key_phrase_extraction import process_key_phrase_extraction
from ocr import process_ocr
from pending_index_completion import process_pending_index_completion
from pending_index_trigger import process_pending_index_trigger

from common.payloads.pending_index_trigger import PendingIndexTriggerPayload

from common.payloads.header import TaskEnum

logging.basicConfig(level=logging.INFO)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="text_split", methods=[func.HttpMethod.POST])
async def text_split(req: func.HttpRequest) -> func.HttpResponse:
    """Extract the content from a document using ADI."""

    try:
        req_body = req.get_json()
        values = req_body.get("values")
        text_split_config = req.headers
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug(f"Input Values: {values}")

        record_tasks = []

        for value in values:
            record_tasks.append(
                asyncio.create_task(process_text_split(value, text_split_config))
            )

        results = await asyncio.gather(*record_tasks)
        logging.debug(f"Results: {results}")

        return func.HttpResponse(
            json.dumps({"values": results}),
            status_code=200,
            mimetype="application/json",
        )


@app.route(route="ai_search_2_compass", methods=[func.HttpMethod.POST])
async def ai_search_2_compass(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    """HTTP trigger for AI Search 2 Compass function.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object."""
    logging.info("Python HTTP trigger function processed a request.")

    try:
        req_body = req.get_json()
        values = req_body.get("values")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        for value in values:
            record_tasks.append(asyncio.create_task(process_ai_search_2_compass(value)))

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)
        vectorised_tasks = {"values": results}

        return func.HttpResponse(
            json.dumps(vectorised_tasks), status_code=200, mimetype="application/json"
        )


@app.route(route="adi_2_ai_search", methods=[func.HttpMethod.POST])
async def adi_2_ai_search(req: func.HttpRequest) -> func.HttpResponse:
    """Extract the content from a document using ADI."""

    try:
        req_body = req.get_json()
        values = req_body.get("values")
        adi_config = req.headers

        chunk_by_page = adi_config.get("chunk_by_page", "False").lower() == "true"
        logging.info(f"Chunk by Page: {chunk_by_page}")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        for value in values:
            record_tasks.append(
                asyncio.create_task(
                    process_adi_2_ai_search(value, chunk_by_page=chunk_by_page)
                )
            )

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)

        return func.HttpResponse(
            json.dumps({"values": results}),
            status_code=200,
            mimetype="application/json",
        )


@app.route(route="pre_embedding_cleaner", methods=[func.HttpMethod.POST])
async def pre_embedding_cleaner(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger for data cleanup function.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object."""
    logging.info("Python HTTP trigger data cleanup function processed a request.")

    try:
        req_body = req.get_json()
        values = req_body.get("values")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        for value in values:
            record_tasks.append(
                asyncio.create_task(process_pre_embedding_cleaner(value))
            )

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)
        cleaned_tasks = {"values": results}

        return func.HttpResponse(
            json.dumps(cleaned_tasks), status_code=200, mimetype="application/json"
        )


@app.route(route="keyphrase_extractor", methods=[func.HttpMethod.POST])
async def keyphrase_extractor(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger for data cleanup function.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object."""
    logging.info("Python HTTP trigger data cleanup function processed a request.")

    try:
        req_body = req.get_json()
        values = req_body.get("values")
        logging.info(req_body)
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        for value in values:
            record_tasks.append(
                asyncio.create_task(process_key_phrase_extraction(value))
            )

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)
        cleaned_tasks = {"values": results}

        return func.HttpResponse(
            json.dumps(cleaned_tasks), status_code=200, mimetype="application/json"
        )


@app.route(route="ocr", methods=[func.HttpMethod.POST])
async def ocr(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger for data cleanup function.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object."""
    logging.info("Python HTTP trigger data cleanup function processed a request.")

    try:
        req_body = req.get_json()
        values = req_body.get("values")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        for value in values:
            record_tasks.append(asyncio.create_task(process_ocr(value)))

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)
        cleaned_tasks = {"values": results}

        return func.HttpResponse(
            json.dumps(cleaned_tasks), status_code=200, mimetype="application/json"
        )


@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="pending_index_trigger",
    connection="ServiceBusTrigger",
)
async def pending_index_trigger(msg: func.ServiceBusMessage):
    logging.info(
        f"trigger-indexer: Python ServiceBus queue trigger processed message: {msg}"
    )
    try:
        payload = PendingIndexTriggerPayload.from_service_bus_message(msg)
        await process_pending_index_trigger(payload)
    except ValueError as ve:
        logging.error(f"ValueError: {ve}")
    except Exception as e:
        logging.error(f"Error processing ServiceBus message: {e}")

        if "On-demand indexer invocation is permitted every 180 seconds" in str(e):
            logging.warning(
                f"Indexer invocation limit reached: {e}. Scheduling a retry."
            )
            service_bus_helper = ServiceBusHelper()
            message = PendingIndexTriggerPayload(
                header=payload.header, body=payload.body, errors=[]
            )
            queue = TaskEnum.PENDING_INDEX_TRIGGER.value
            minutes = 2 ** (11 - payload.header.retries_remaining)
            enqueue_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            await service_bus_helper.send_message_to_service_bus_queue(
                queue, message, enqueue_time=enqueue_time
            )
        else:
            raise e


@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="pending_index_completion",
    connection="ServiceBusTrigger",
)
async def pending_index_completion(msg: func.ServiceBusMessage):
    logging.info(
        f"indexer-polling-trigger: Python ServiceBus queue trigger processed message: {msg}"
    )

    try:
        payload = PendingIndexTriggerPayload.from_service_bus_message(msg)
        await process_pending_index_completion(payload)
    except ValueError as ve:
        logging.error(f"ValueError: {ve}")
    except Exception as e:
        logging.error(f"Error processing ServiceBus message: {e}")
        if "The operation has timed out" in str(e):
            logging.error("The operation has timed out.")
        raise e
