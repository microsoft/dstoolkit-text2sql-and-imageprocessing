# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import azure.functions as func
import logging
import json
import asyncio

from figure_analysis import FigureAnalysis
from layout_and_figure_merger import LayoutAndFigureMerger
from layout_analysis import process_layout_analysis
from mark_up_cleaner import MarkUpCleaner
from semantic_text_chunker import process_semantic_text_chunker, SemanticTextChunker

logging.basicConfig(level=logging.DEBUG)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="layout_analysis", methods=[func.HttpMethod.POST])
async def layout_analysis(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        values = req_body.get("values")
        adi_config = req.headers

        page_wise = adi_config.get("chunk_by_page", "False").lower() == "true"
        extract_figures = adi_config.get("extract_figures", "True").lower() == "true"
        logging.info(f"Chunk by Page: {page_wise}")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.info("Input Values: %s", values)

        record_tasks = []

        for value in values:
            record_tasks.append(
                asyncio.create_task(
                    process_layout_analysis(
                        value, page_wise=page_wise, extract_figures=extract_figures
                    )
                )
            )

        results = await asyncio.gather(*record_tasks)
        logging.info("Results: %s", results)

        return func.HttpResponse(
            json.dumps({"values": results}),
            status_code=200,
            mimetype="application/json",
        )


@app.route(route="figure_analysis", methods=[func.HttpMethod.POST])
async def figure_analysis(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        values = req_body.get("values")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.info("Input Values: %s", values)

        record_tasks = []

        figure_analysis_processor = FigureAnalysis()

        for value in values:
            record_tasks.append(
                asyncio.create_task(figure_analysis_processor.analyse(value))
            )

        results = await asyncio.gather(*record_tasks)
        logging.info("Results: %s", results)

        return func.HttpResponse(
            json.dumps({"values": results}),
            status_code=200,
            mimetype="application/json",
        )


@app.route(route="layout_and_figure_merger", methods=[func.HttpMethod.POST])
async def layout_and_figure_merger(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        values = req_body.get("values")
    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.info("Input Values: %s", values)

        record_tasks = []

        layout_and_figure_merger_processor = LayoutAndFigureMerger()

        for value in values:
            record_tasks.append(
                asyncio.create_task(layout_and_figure_merger_processor.merge(value))
            )

        results = await asyncio.gather(*record_tasks)
        logging.info("Results: %s", results)

        return func.HttpResponse(
            json.dumps({"values": results}),
            status_code=200,
            mimetype="application/json",
        )


@app.route(route="mark_up_cleaner", methods=[func.HttpMethod.POST])
async def mark_up_cleaner(req: func.HttpRequest) -> func.HttpResponse:
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

        mark_up_cleaner_processor = MarkUpCleaner()

        for value in values:
            record_tasks.append(
                asyncio.create_task(mark_up_cleaner_processor.clean(value))
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

        similarity_threshold = float(
            semantic_text_chunker_config.get("similarity_threshold", 0.8)
        )
        max_chunk_tokens = int(
            semantic_text_chunker_config.get("max_chunk_tokens", 500)
        )
        min_chunk_tokens = int(semantic_text_chunker_config.get("min_chunk_tokens", 50))

    except ValueError:
        return func.HttpResponse(
            "Please valid Custom Skill Payload in the request body", status_code=400
        )
    else:
        logging.debug("Input Values: %s", values)

        record_tasks = []

        semantic_text_chunker_processor = SemanticTextChunker(
            similarity_threshold=similarity_threshold,
            max_chunk_tokens=max_chunk_tokens,
            min_chunk_tokens=min_chunk_tokens,
        )

        for value in values:
            record_tasks.append(
                asyncio.create_task(
                    process_semantic_text_chunker(
                        value, semantic_text_chunker_processor
                    )
                )
            )

        results = await asyncio.gather(*record_tasks)
        logging.debug("Results: %s", results)
        cleaned_tasks = {"values": results}

        return func.HttpResponse(
            json.dumps(cleaned_tasks), status_code=200, mimetype="application/json"
        )
