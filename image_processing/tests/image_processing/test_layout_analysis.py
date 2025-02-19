# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import pytest
import tempfile
import base64
from unittest.mock import AsyncMock

# Import the functions/classes under test.
from layout_analysis import (
    process_layout_analysis,
    LayoutAnalysis,
)

# --- Dummy classes to simulate ADI results and figures ---


class DummyPage:
    def __init__(self, offset, length, page_number):
        # Simulate a page span as a dictionary.
        self.spans = [{"offset": offset, "length": length}]
        self.page_number = page_number


class DummyRegion:
    def __init__(self, page_number):
        self.page_number = page_number


class DummyCaption:
    def __init__(self, content):
        self.content = content


class DummyFigure:
    def __init__(self, id, offset, length, page_number, caption_content):
        self.id = id  # note: process_figures_from_extracted_content checks "if figure.id is None"
        self.bounding_regions = [DummyRegion(page_number)]
        self.caption = DummyCaption(caption_content)
        self.spans = [{"offset": offset, "length": length}]


class DummyResult:
    def __init__(self, content, pages, figures, model_id="model123"):
        self.content = content
        self.pages = pages
        self.figures = figures
        self.model_id = model_id


# --- Dummy StorageAccountHelper for testing purposes ---
class DummyStorageAccountHelper:
    @property
    def account_url(self):
        return "http://dummy.storage"

    async def upload_blob(self, container, blob, data, content_type):
        # Simulate a successful upload returning a URL.
        return f"http://dummy.url/{blob}"

    async def download_blob_to_temp_dir(self, source, container, target_file_name):
        # Write dummy content to a temp file and return its path along with empty metadata.
        temp_file_path = os.path.join(tempfile.gettempdir(), target_file_name)
        with open(temp_file_path, "wb") as f:
            f.write(b"dummy file content")
        return temp_file_path, {}

    async def add_metadata_to_blob(self, source, container, metadata, upsert=False):
        # Dummy method; do nothing.
        return


# --- Fixtures and environment setup ---
@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv("StorageAccount__Name", "dummyaccount")
    monkeypatch.setenv(
        "AIService__DocumentIntelligence__Endpoint", "http://dummy.ai.endpoint"
    )


@pytest.fixture
def dummy_storage_helper():
    return DummyStorageAccountHelper()


# --- Tests for LayoutAnalysis and process_layout_analysis ---


def test_extract_file_info():
    # Given a typical blob URL, extract_file_info should correctly set properties.
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.pdf"
    la = LayoutAnalysis(record_id=1, source=source)
    la.extract_file_info()
    assert la.blob == "path/to/file.pdf"
    assert la.container == "container"
    assert la.images_container == "container-figures"
    assert la.file_extension == "pdf"
    assert la.target_file_name == "1.pdf"


# Test non-page-wise analysis without figures.
@pytest.mark.asyncio
async def test_analyse_non_page_wise_no_figures(monkeypatch, dummy_storage_helper):
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=False, extract_figures=True, record_id=123, source=source
    )
    la.extract_file_info()
    # Patch get_storage_account_helper to return our dummy helper.
    monkeypatch.setattr(
        la, "get_storage_account_helper", AsyncMock(return_value=dummy_storage_helper)
    )
    # Patch download_blob_to_temp_dir to simulate a successful download.
    monkeypatch.setattr(
        dummy_storage_helper,
        "download_blob_to_temp_dir",
        AsyncMock(return_value=("/tmp/dummy.txt", {})),
    )
    # Patch analyse_document to simulate a successful ADI analysis.
    dummy_result = DummyResult(
        content="Full document content", pages=[DummyPage(0, 21, None)], figures=[]
    )

    async def dummy_analyse_document(file_path):
        la.result = dummy_result
        la.operation_id = "op123"

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document)
    # Patch process_figures_from_extracted_content to do nothing (since there are no figures).
    monkeypatch.setattr(la, "process_figures_from_extracted_content", AsyncMock())
    result = await la.analyse()
    assert result["recordId"] == 123
    data = result["data"]
    # In non-page-wise mode, the output record is a NonPageWiseContentHolder
    assert "layout" in data
    layout = data["layout"]
    assert layout["content"] == "Full document content"
    # No figures were processed.
    assert layout.get("figures", []) == []
    assert result["errors"] is None


# Test page-wise analysis without figures.
@pytest.mark.asyncio
async def test_analyse_page_wise_no_figures(monkeypatch, dummy_storage_helper):
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=True, extract_figures=True, record_id=456, source=source
    )
    la.extract_file_info()
    monkeypatch.setattr(
        la, "get_storage_account_helper", AsyncMock(return_value=dummy_storage_helper)
    )
    monkeypatch.setattr(
        dummy_storage_helper,
        "download_blob_to_temp_dir",
        AsyncMock(return_value=("/tmp/dummy.txt", {})),
    )
    # Create a dummy result with one page and no figures.
    dummy_page = DummyPage(0, 12, 1)
    dummy_result = DummyResult(content="Page content", pages=[dummy_page], figures=[])

    async def dummy_analyse_document(file_path):
        la.result = dummy_result
        la.operation_id = "op456"

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document)
    result = await la.analyse()
    assert result["recordId"] == 456
    data = result["data"]
    # In page-wise mode, the output should have a "page_wise_layout" key.
    assert "page_wise_layout" in data
    layouts = data["page_wise_layout"]
    assert len(layouts) == 1
    layout = layouts[0]
    # The content is extracted from dummy_result.content using the page span.
    expected_content = dummy_result.content[0:12]
    assert layout["content"] == expected_content
    assert layout["page_number"] == 1
    assert result["errors"] is None


# Test page-wise analysis with figures (covering figure download and upload).
@pytest.mark.asyncio
async def test_analyse_page_wise_with_figures(monkeypatch, dummy_storage_helper):
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=True, extract_figures=True, record_id=789, source=source
    )
    la.extract_file_info()
    monkeypatch.setattr(
        la, "get_storage_account_helper", AsyncMock(return_value=dummy_storage_helper)
    )
    monkeypatch.setattr(
        dummy_storage_helper,
        "download_blob_to_temp_dir",
        AsyncMock(return_value=("/tmp/dummy.txt", {})),
    )
    # Create a dummy page and a dummy figure.
    dummy_page = DummyPage(0, 12, 1)
    dummy_figure = DummyFigure(
        "fig1", offset=5, length=5, page_number=1, caption_content="Caption text"
    )
    dummy_result = DummyResult(
        content="Page content", pages=[dummy_page], figures=[dummy_figure]
    )

    async def dummy_analyse_document(file_path):
        la.result = dummy_result
        la.operation_id = "op789"

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document)
    # Patch download_figure_image to simulate downloading image bytes.
    monkeypatch.setattr(
        la, "download_figure_image", AsyncMock(return_value=b"fake_image")
    )
    # Patch upload_blob to simulate a successful upload.
    monkeypatch.setattr(
        dummy_storage_helper,
        "upload_blob",
        AsyncMock(return_value="http://dummy.url/fig1.png"),
    )
    result = await la.analyse()
    assert result["recordId"] == 789
    data = result["data"]
    assert "page_wise_layout" in data
    layouts = data["page_wise_layout"]
    # The page layout should have a figures list containing our processed figure.
    assert len(layouts) == 1
    layout = layouts[0]
    assert "figures" in layout
    figures_list = layout["figures"]
    assert len(figures_list) == 1
    figure_data = figures_list[0]
    assert figure_data["figure_id"] == "fig1"
    # The data field should contain the base64-encoded image.
    expected_b64 = base64.b64encode(b"fake_image").decode("utf-8")
    assert figure_data["data"] == expected_b64
    # Verify that the container, blob, and caption are set as expected.
    assert figure_data["container"] == f"{la.container}-figures"
    expected_blob = f"{la.blob}/fig1.png"
    assert figure_data["blob"] == expected_blob
    assert figure_data["caption"] == "Caption text"
    assert result["errors"] is None


# Test failure during blob download.
@pytest.mark.asyncio
async def test_analyse_download_blob_failure(monkeypatch, dummy_storage_helper):
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=False, extract_figures=True, record_id=321, source=source
    )
    la.extract_file_info()
    monkeypatch.setattr(
        la, "get_storage_account_helper", AsyncMock(return_value=dummy_storage_helper)
    )
    # Simulate a failure in download_blob_to_temp_dir.
    monkeypatch.setattr(
        dummy_storage_helper,
        "download_blob_to_temp_dir",
        AsyncMock(side_effect=Exception("Download error")),
    )
    result = await la.analyse()
    assert result["recordId"] == 321
    assert result["data"] is None
    assert result["errors"] is not None
    assert "Failed to download the blob" in result["errors"][0]["message"]


# Test failure during analyse_document (simulate ADI failure) and ensure metadata is updated.
@pytest.mark.asyncio
async def test_analyse_document_failure(monkeypatch, dummy_storage_helper):
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=False, extract_figures=True, record_id=654, source=source
    )
    la.extract_file_info()
    monkeypatch.setattr(
        la, "get_storage_account_helper", AsyncMock(return_value=dummy_storage_helper)
    )
    monkeypatch.setattr(
        dummy_storage_helper,
        "download_blob_to_temp_dir",
        AsyncMock(return_value=("/tmp/dummy.txt", {})),
    )

    # Simulate analyse_document throwing an exception.
    async def dummy_analyse_document_failure(file_path):
        raise Exception("Analyse document error")

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document_failure)
    # Track whether add_metadata_to_blob is called.
    metadata_called = False

    async def dummy_add_metadata(source, container, metadata, upsert=False):
        nonlocal metadata_called
        metadata_called = True

    monkeypatch.setattr(
        dummy_storage_helper, "add_metadata_to_blob", dummy_add_metadata
    )
    result = await la.analyse()
    assert result["recordId"] == 654
    assert result["data"] is None
    assert result["errors"] is not None
    assert (
        "Failed to analyze the document with Azure Document Intelligence"
        in result["errors"][0]["message"]
    )
    assert metadata_called is True


# Test failure during processing of extracted content (e.g. page-wise content creation).
@pytest.mark.asyncio
async def test_analyse_processing_content_failure(monkeypatch, dummy_storage_helper):
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=True, extract_figures=True, record_id=987, source=source
    )
    la.extract_file_info()
    monkeypatch.setattr(
        la, "get_storage_account_helper", AsyncMock(return_value=dummy_storage_helper)
    )
    monkeypatch.setattr(
        dummy_storage_helper,
        "download_blob_to_temp_dir",
        AsyncMock(return_value=("/tmp/dummy.txt", {})),
    )
    # Simulate a successful analyse_document.
    dummy_page = DummyPage(0, 12, 1)
    dummy_result = DummyResult(content="Page content", pages=[dummy_page], figures=[])

    async def dummy_analyse_document(file_path):
        la.result = dummy_result
        la.operation_id = "op987"

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document)

    # Patch create_page_wise_content to raise an exception.
    def raise_exception():
        raise Exception("Processing error")

    monkeypatch.setattr(la, "create_page_wise_content", raise_exception)
    result = await la.analyse()
    assert result["recordId"] == 987
    assert result["data"] is None
    assert result["errors"] is not None
    assert "Failed to process the extracted content" in result["errors"][0]["message"]


# Test process_layout_analysis when 'source' is missing (KeyError branch).
@pytest.mark.asyncio
async def test_process_layout_analysis_missing_source():
    record = {"recordId": "111", "data": {}}  # missing 'source' key
    result = await process_layout_analysis(record)
    assert result["recordId"] == "111"
    assert result["data"] is None
    assert result["errors"] is not None
    assert "Pass a valid source" in result["errors"][0]["message"]
