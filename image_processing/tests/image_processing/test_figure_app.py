# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import pytest

import function_app
from function_app import (
    layout_analysis,
    figure_analysis,
    layout_and_figure_merger,
    mark_up_cleaner,
    semantic_text_chunker,
    FigureAnalysis,
    LayoutAndFigureMerger,
    MarkUpCleaner,
)


# A simple dummy HttpRequest-like object that mimics what
# azure.functions.HttpRequest provides.
class DummyRequest:
    def __init__(self, method, url, headers, body):
        self.method = method
        self.url = url
        self.headers = headers
        self._body = body

    def get_json(self):
        return json.loads(self._body.decode("utf8"))

    def get_body(self):
        return self._body


# ----------------------------
# Tests for layout_analysis
# ----------------------------
@pytest.mark.asyncio
async def test_layout_analysis_valid(monkeypatch):
    # Create a dummy async function to replace process_layout_analysis.
    async def dummy_process_layout_analysis(value, page_wise, extract_figures):
        return {
            "processed": True,
            "value": value,
            "page_wise": page_wise,
            "extract_figures": extract_figures,
        }

    # Patch the dependency in the module namespace.
    monkeypatch.setattr(
        function_app, "process_layout_analysis", dummy_process_layout_analysis
    )

    req_body = {"values": [{"id": "1", "data": "test data"}]}
    headers = {"chunk_by_page": "true", "extract_figures": "false"}
    req = DummyRequest(
        method="POST",
        url="/layout_analysis",
        headers=headers,
        body=json.dumps(req_body).encode("utf8"),
    )

    resp = await layout_analysis(req)
    assert resp.status_code == 200

    resp_body = json.loads(resp.get_body().decode("utf8"))
    # Check that the returned value includes our dummy output.
    assert "values" in resp_body
    result = resp_body["values"][0]
    assert result["processed"] is True
    # Confirm that header conversion worked:
    assert result["page_wise"] is True
    assert result["extract_figures"] is False


@pytest.mark.asyncio
async def test_layout_analysis_invalid_json():
    # Create a dummy request that raises ValueError on get_json()
    class DummyInvalidRequest:
        def __init__(self):
            self.headers = {}

        def get_json(self):
            raise ValueError("Invalid JSON")

    req = DummyInvalidRequest()
    resp = await layout_analysis(req)
    # The function should return a 400 error if JSON is invalid.
    assert resp.status_code == 400
    # Optionally, you could check that the response body contains the expected error message.
    assert "Custom Skill Payload" in resp.get_body().decode("utf8")


# ----------------------------
# Tests for figure_analysis
# ----------------------------
@pytest.mark.asyncio
async def test_figure_analysis_valid(monkeypatch):
    async def dummy_analyse(self, value):
        return {"fig_analyse": True, "value": value}

    # Patch the 'analyse' method of FigureAnalysis.
    monkeypatch.setattr(FigureAnalysis, "analyse", dummy_analyse)

    req_body = {"values": [{"id": "1", "data": "test data"}]}
    req = DummyRequest(
        method="POST",
        url="/figure_analysis",
        headers={},
        body=json.dumps(req_body).encode("utf8"),
    )

    resp = await figure_analysis(req)
    assert resp.status_code == 200

    resp_body = json.loads(resp.get_body().decode("utf8"))
    assert "values" in resp_body
    result = resp_body["values"][0]
    assert result["fig_analyse"] is True


# ----------------------------
# Tests for layout_and_figure_merger
# ----------------------------
@pytest.mark.asyncio
async def test_layout_and_figure_merger_valid(monkeypatch):
    async def dummy_merge(self, value):
        return {"merged": True, "value": value}

    monkeypatch.setattr(LayoutAndFigureMerger, "merge", dummy_merge)

    req_body = {"values": [{"id": "1", "data": "test data"}]}
    req = DummyRequest(
        method="POST",
        url="/layout_and_figure_merger",
        headers={},
        body=json.dumps(req_body).encode("utf8"),
    )

    resp = await layout_and_figure_merger(req)
    assert resp.status_code == 200

    resp_body = json.loads(resp.get_body().decode("utf8"))
    assert "values" in resp_body
    result = resp_body["values"][0]
    assert result["merged"] is True


# ----------------------------
# Tests for mark_up_cleaner
# ----------------------------
@pytest.mark.asyncio
async def test_mark_up_cleaner_valid(monkeypatch):
    async def dummy_clean(self, value):
        return {"cleaned": True, "value": value}

    monkeypatch.setattr(MarkUpCleaner, "clean", dummy_clean)

    req_body = {"values": [{"id": "1", "data": "some markup <b>text</b>"}]}
    req = DummyRequest(
        method="POST",
        url="/mark_up_cleaner",
        headers={},
        body=json.dumps(req_body).encode("utf8"),
    )

    resp = await mark_up_cleaner(req)
    assert resp.status_code == 200

    resp_body = json.loads(resp.get_body().decode("utf8"))
    assert "values" in resp_body
    result = resp_body["values"][0]
    assert result["cleaned"] is True


# ----------------------------
# Tests for semantic_text_chunker
# ----------------------------
@pytest.mark.asyncio
async def test_semantic_text_chunker_valid(monkeypatch):
    async def dummy_process_semantic_text_chunker(value, processor):
        return {"chunked": True, "value": value}

    monkeypatch.setattr(
        function_app,
        "process_semantic_text_chunker",
        dummy_process_semantic_text_chunker,
    )

    headers = {
        "similarity_threshold": "0.9",
        "max_chunk_tokens": "600",
        "min_chunk_tokens": "60",
    }
    req_body = {"values": [{"id": "1", "text": "test text for chunking"}]}
    req = DummyRequest(
        method="POST",
        url="/semantic_text_chunker",
        headers=headers,
        body=json.dumps(req_body).encode("utf8"),
    )

    resp = await semantic_text_chunker(req)
    assert resp.status_code == 200

    resp_body = json.loads(resp.get_body().decode("utf8"))
    assert "values" in resp_body
    result = resp_body["values"][0]
    assert result["chunked"] is True


@pytest.mark.asyncio
async def test_semantic_text_chunker_invalid_json():
    # Create a dummy request that raises ValueError when get_json is called.
    class DummyInvalidRequest:
        def __init__(self):
            self.headers = {}

        def get_json(self):
            raise ValueError("Invalid JSON")

    req = DummyInvalidRequest()
    resp = await semantic_text_chunker(req)
    assert resp.status_code == 400
