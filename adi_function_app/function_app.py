# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import azure.functions as func
import logging
import json
import asyncio

from adi_2_ai_search import process_adi_2_ai_search
from pre_embedding_cleaner import process_pre_embedding_cleaner
from key_phrase_extraction import process_key_phrase_extraction
from semantic_text_chunker import process_semantic_text_chunker, SemanticTextChunker

logging.basicConfig(level=logging.DEBUG)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


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


@app.route(route="semantic_text_chunker", methods=[func.HttpMethod.POST])
async def semantic_text_chunker(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger for text chunking function.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object."""
    logging.info("Python HTTP trigger text chunking function processed a request.")

    try:
        req_body = req.get_json()
        values = req_body.get("values")

        semantic_text_chunker_config = req.headers

        num_surrounding_sentences = semantic_text_chunker_config.get(
            "num_surrounding_sentences", 1
        )
        similarity_threshold = semantic_text_chunker_config.get(
            "similarity_threshold", 0.8
        )
        max_chunk_tokens = semantic_text_chunker_config.get("max_chunk_tokens", 500)

    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        semantic_text_chunker = SemanticTextChunker(
            num_surrounding_sentences=num_surrounding_sentences,
            similarity_threshold=similarity_threshold,
            max_chunk_tokens=max_chunk_tokens,
        )

        for value in values:
            record_tasks.append(
                asyncio.create_task(
                    process_semantic_text_chunker(value, semantic_text_chunker)
                )
            )

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)
        cleaned_tasks = {"values": results}

        return func.HttpResponse(
            json.dump(cleaned_tasks), status_code=200, mimetype="application/json"
        )


@app.route(route="key_phrase_extractor", methods=[func.HttpMethod.POST])
async def key_phrase_extractor(req: func.HttpRequest) -> func.HttpResponse:
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

        return func.HttpResponse(
            json.dumps({"values": results}),
            status_code=200,
            mimetype="application/json",
        )
