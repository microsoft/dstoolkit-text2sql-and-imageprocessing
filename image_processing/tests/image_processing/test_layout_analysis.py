# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import pytest
import tempfile
import base64
from unittest.mock import AsyncMock

from layout_analysis import (
    process_layout_analysis,
    LayoutAnalysis,
)

from layout_holders import LayoutHolder


# --- Dummy classes to simulate ADI results and figures ---
class DummySpan:
    def __init__(self, offset, length):
        self.offset = offset
        self.length = length


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


class DummyPoller:
    def __init__(self, result, operation_id):
        self._result = result
        self.details = {"operation_id": operation_id}

    async def result(self):
        return self._result


class DummyDocIntelligenceClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def begin_analyze_document(self, **kwargs):
        # Create a dummy page spanning the first 5 characters.
        dummy_page = DummyPage(0, 5, 1)
        dummy_result = DummyResult("HelloWorld", pages=[dummy_page], figures=[])
        return DummyPoller(dummy_result, "dummy_op")


class DummyFigure:
    def __init__(self, id, offset, length, page_number, caption_content):
        self.id = id  # note: process_figures_from_extracted_content checks "if figure.id is None"
        self.bounding_regions = [DummyRegion(page_number)]
        self.caption = DummyCaption(caption_content)
        self.spans = [DummySpan(offset, length)]


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
        content="Full document content", pages=[DummyPage(0, 21, 1)], figures=[]
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
    # Verify that the caption are set as expected.
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


@pytest.mark.asyncio
async def test_analyse_document_success(monkeypatch, tmp_path):
    # Create a temporary file with dummy content.
    tmp_file = tmp_path / "dummy.txt"
    tmp_file.write_bytes(b"dummy content")

    la = LayoutAnalysis(
        record_id=999,
        source="https://dummyaccount.blob.core.windows.net/container/path/to/dummy.txt",
    )

    # Use an async function to return our dummy Document Intelligence client.
    async def dummy_get_doc_intelligence_client():
        return DummyDocIntelligenceClient()

    monkeypatch.setattr(
        la, "get_document_intelligence_client", dummy_get_doc_intelligence_client
    )

    await la.analyse_document(str(tmp_file))

    assert la.result is not None
    assert la.operation_id == "dummy_op"
    # Check that the dummy result contains the expected content.
    assert la.result.content == "HelloWorld"


def test_create_page_wise_content():
    # Test create_page_wise_content using a dummy result with one page.
    la = LayoutAnalysis(record_id=100, source="dummy")

    # Create a dummy result with content "HelloWorld"
    # and a page with a span from index 0 with length 5.
    class DummyResultContent:
        pass

    dummy_result = DummyResultContent()
    dummy_result.content = "HelloWorld"
    dummy_result.pages = [DummyPage(0, 5, 1)]
    la.result = dummy_result

    layouts = la.create_page_wise_content()
    assert isinstance(layouts, list)
    assert len(layouts) == 1
    layout = layouts[0]
    # The page content should be the substring "Hello"
    assert layout.content == "Hello"
    assert layout.page_number == 1
    assert layout.page_offsets == 0


def test_create_page_number_tracking_holder():
    # Create a LayoutAnalysis instance.
    la = LayoutAnalysis(record_id=200, source="dummy")

    # Create a dummy result with content and pages.
    # For this test, the first page's content slice will be "HelloWorld" (from index 0 with length 10),
    # so the starting sentence extracted should be "HelloWorld".
    class DummyResultContent:
        pass

    dummy_result = DummyResultContent()
    dummy_result.content = "HelloWorld. This is a test sentence."
    # DummyPage creates a page with spans as a list of dictionaries.
    dummy_result.pages = [DummyPage(0, 36, 1)]
    la.result = dummy_result

    page_number_trackers = la.create_page_number_tracking_holder()
    assert len(page_number_trackers) == 1
    tracker = page_number_trackers[0]
    assert tracker.page_number == 1
    assert tracker.page_content == "HelloWorld. This is a test sentence."


def test_create_page_number_tracking_holder_multiple_pages():
    # Create a LayoutAnalysis instance.
    la = LayoutAnalysis(record_id=300, source="dummy")

    # Create a dummy result with content spanning two pages.
    # Use DummyPage to simulate pages; DummyPage expects "spans" as a list of dicts.
    class DummyResultContent:
        pass

    dummy_result = DummyResultContent()
    # Define content as two parts:
    # Page 1: Offset 0, length 10 gives "Page one." (starting sentence "Page one")
    # Page 2: Offset 10, length 15 gives " Page two text" (starting sentence " Page two text")
    dummy_result.content = "Page one.Page two text and more content. This is more random content that is on page 2."
    dummy_result.pages = [
        DummyPage(0, 9, 1),  # "Page one." (9 characters: indices 0-8)
        DummyPage(9, 78, 2),  # "Page two text and" (16 characters: indices 9-24)
    ]
    la.result = dummy_result

    # Call create_page_number_tracking_holder and check results.
    page_number_trackers = la.create_page_number_tracking_holder()
    assert len(page_number_trackers) == 2

    # For page 1, the substring is "Page one." -> split on "." gives "Page one"
    assert page_number_trackers[0].page_number == 1
    assert page_number_trackers[0].page_content == "Page one."

    # For page 2, the substring is "Page two text and" -> split on "." gives the entire string
    assert page_number_trackers[1].page_number == 2
    # We strip potential leading/trailing spaces for validation.
    assert (
        page_number_trackers[1].page_content.strip()
        == "Page two text and more content. This is more random content that is on page 2."
    )


# Test for download_figure_image with retry logic
@pytest.mark.asyncio
async def test_download_figure_image_with_retry(monkeypatch):
    """Test the download_figure_image method with retry logic."""
    la = LayoutAnalysis(record_id=101, source="dummy")
    la.operation_id = "op101"
    la.result = DummyResult("content", [], [], model_id="model101")

    # Create a counter to track number of attempts
    call_count = 0

    # Mock document_intelligence_client.get_analyze_result_figure
    class MockResponse:
        def __init__(self):
            self.chunks = [b"chunk1", b"chunk2"]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.chunks:
                raise StopAsyncIteration
            return self.chunks.pop(0)

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get_analyze_result_figure(self, model_id, result_id, figure_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Fail on first attempt
                raise Exception("Temporary failure")
            # Succeed on subsequent attempts
            return MockResponse()

    # Patch get_document_intelligence_client to return our mock
    async def mock_get_client():
        return MockClient()

    monkeypatch.setattr(la, "get_document_intelligence_client", mock_get_client)

    # Call the method - should succeed after retry
    result = await la.download_figure_image("fig1")

    # Check that it was called more than once (at least one retry)
    assert call_count > 1
    # Check the result contains both chunks
    assert result == b"chunk1chunk2"


# Test for non-page-wise analysis with figures
@pytest.mark.asyncio
async def test_analyse_non_page_wise_with_figures(monkeypatch, dummy_storage_helper):
    """Test non-page-wise analysis with figures."""
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=False, extract_figures=True, record_id=102, source=source
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

    # Create a dummy result with content and a figure
    dummy_page = DummyPage(0, 20, 1)
    dummy_figure = DummyFigure(
        "fig102",
        offset=10,
        length=5,
        page_number=1,
        caption_content="Figure 102 caption",
    )
    dummy_result = DummyResult(
        content="Full document content", pages=[dummy_page], figures=[dummy_figure]
    )

    async def dummy_analyse_document(file_path):
        la.result = dummy_result
        la.operation_id = "op102"

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document)

    # Mock figure download and upload
    monkeypatch.setattr(
        la, "download_figure_image", AsyncMock(return_value=b"figure102_image_data")
    )
    monkeypatch.setattr(
        dummy_storage_helper,
        "upload_blob",
        AsyncMock(return_value="http://dummy.url/fig102.png"),
    )

    result = await la.analyse()

    assert result["recordId"] == 102
    assert result["data"] is not None
    # In non-page-wise mode, we should have layout and page_number_tracking_holders
    assert "layout" in result["data"]
    assert "page_number_tracking_holders" in result["data"]

    # Verify figure was processed
    layout = result["data"]["layout"]
    assert "figures" in layout
    figures = layout["figures"]
    assert len(figures) == 1
    assert figures[0]["figure_id"] == "fig102"
    assert figures[0]["caption"] == "Figure 102 caption"
    expected_b64 = base64.b64encode(b"figure102_image_data").decode("utf-8")
    assert figures[0]["data"] == expected_b64


# Test for when extract_figures is False
@pytest.mark.asyncio
async def test_analyse_without_extracting_figures(monkeypatch, dummy_storage_helper):
    """Test analysis when extract_figures is False."""
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=True, extract_figures=False, record_id=103, source=source
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

    # Create a dummy result with content and a figure
    dummy_page = DummyPage(0, 10, 1)
    dummy_figure = DummyFigure(
        "fig103",
        offset=5,
        length=3,
        page_number=1,
        caption_content="Figure 103 caption",
    )
    dummy_result = DummyResult(
        content="Page content", pages=[dummy_page], figures=[dummy_figure]
    )

    async def dummy_analyse_document(file_path):
        la.result = dummy_result
        la.operation_id = "op103"

    monkeypatch.setattr(la, "analyse_document", dummy_analyse_document)

    # Add spy on process_figures_from_extracted_content to ensure it's not called
    process_figures_spy = AsyncMock()
    monkeypatch.setattr(
        la, "process_figures_from_extracted_content", process_figures_spy
    )

    result = await la.analyse()

    # Verify the function was not called
    process_figures_spy.assert_not_called()

    assert result["recordId"] == 103
    assert result["data"] is not None
    # Verify we have page_wise_layout
    assert "page_wise_layout" in result["data"]
    layouts = result["data"]["page_wise_layout"]
    assert len(layouts) == 1
    # Each layout should have an empty figures list
    assert layouts[0]["figures"] == []


# Test for HTML comment handling in create_page_number_tracking_holder
def test_create_page_number_tracking_holder_html_comments():
    """Test HTML comment handling in page content extraction."""
    la = LayoutAnalysis(record_id=104, source="dummy")

    class DummyResultContent:
        pass

    dummy_result = DummyResultContent()
    # Content with HTML comments
    dummy_result.content = "Before <!-- comment --> After"
    dummy_result.pages = [DummyPage(0, 29, 1)]  # Full content
    la.result = dummy_result

    page_number_trackers = la.create_page_number_tracking_holder()
    assert len(page_number_trackers) == 1
    # HTML comments should be removed
    assert page_number_trackers[0].page_content == "Before  After"


# Test for figure tag handling in create_page_number_tracking_holder
def test_create_page_number_tracking_holder_figure_tags():
    """Test figure tag handling in page content extraction."""
    la = LayoutAnalysis(record_id=105, source="dummy")

    class DummyResultContent:
        pass

    dummy_result = DummyResultContent()
    # Content with figure tags
    dummy_result.content = "Before <figure>Figure content</figure> After"
    dummy_result.pages = [DummyPage(0, 44, 1)]  # Full content
    la.result = dummy_result

    page_number_trackers = la.create_page_number_tracking_holder()
    assert len(page_number_trackers) == 1
    # Figure content should be removed
    assert page_number_trackers[0].page_content == "Before  After"


# Test handling of empty content
def test_create_page_number_tracking_holder_empty_content():
    """Test handling of empty content in page tracking."""
    la = LayoutAnalysis(record_id=106, source="dummy")

    class DummyResultContent:
        pass

    dummy_result = DummyResultContent()
    # Empty content
    dummy_result.content = ""
    dummy_result.pages = [DummyPage(0, 0, 1)]  # Empty content
    la.result = dummy_result

    page_number_trackers = la.create_page_number_tracking_holder()
    assert len(page_number_trackers) == 1
    # Page content should be None for empty content
    assert page_number_trackers[0].page_content is None


# Test for process_layout_analysis with page_wise=True
@pytest.mark.asyncio
async def test_process_layout_analysis_page_wise(monkeypatch):
    """Test process_layout_analysis with page_wise=True."""
    record = {
        "recordId": "107",
        "data": {"source": "https://dummy.blob.core.windows.net/container/blob.pdf"},
    }

    # Create a mock LayoutAnalysis
    mock_layout_analysis = AsyncMock()
    mock_layout_analysis.analyse = AsyncMock(
        return_value={"recordId": "107", "data": {"result": "success"}}
    )

    # Mock the LayoutAnalysis constructor
    def mock_layout_analysis_constructor(*args, **kwargs):
        # Verify page_wise=True was passed
        assert kwargs["page_wise"] is True
        return mock_layout_analysis

    monkeypatch.setattr(
        "layout_analysis.LayoutAnalysis", mock_layout_analysis_constructor
    )

    result = await process_layout_analysis(record, page_wise=True)

    # Verify analyse was called
    mock_layout_analysis.analyse.assert_called_once()
    assert result["recordId"] == "107"
    assert result["data"] == {"result": "success"}


# Test handling figures without captions
@pytest.mark.asyncio
async def test_figure_without_caption(monkeypatch, dummy_storage_helper):
    """Test handling figures without captions."""
    source = "https://dummyaccount.blob.core.windows.net/container/path/to/file.txt"
    la = LayoutAnalysis(
        page_wise=False, extract_figures=True, record_id=108, source=source
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

    # Create a figure without a caption (caption=None)
    dummy_figure = DummyFigure(
        "fig108", offset=5, length=3, page_number=1, caption_content=None
    )
    dummy_result = DummyResult(
        content="Content", pages=[DummyPage(0, 7, 1)], figures=[dummy_figure]
    )

    la.result = dummy_result
    monkeypatch.setattr(
        la, "download_figure_image", AsyncMock(return_value=b"figure108_image_data")
    )

    # Create a minimal layout holder for testing
    layout_holder = LayoutHolder(content="Test", page_number=1, page_offsets=0)

    # Process the figures
    await la.process_figures_from_extracted_content(layout_holder)

    # Check that the figure was processed despite having no caption
    assert len(layout_holder.figures) == 1
    figure = layout_holder.figures[0]
    assert figure.figure_id == "fig108"
    assert figure.caption is None  # Caption should be None
