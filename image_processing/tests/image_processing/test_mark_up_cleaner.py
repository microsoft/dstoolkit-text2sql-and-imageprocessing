# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest
from mark_up_cleaner import MarkUpCleaner
from layout_holders import FigureHolder, ChunkHolder


# Fixtures
@pytest.fixture
def cleaner():
    return MarkUpCleaner()


@pytest.fixture
def sample_text():
    return """
    # Header 1
    Some text.
    ## Header 2
    More text.
    <figure FigureId='12345'></figure>
    """


@pytest.fixture
def figures():
    # We'll use the object-based representation for figures.
    return [
        FigureHolder(
            FigureId="fig1",
            offset=10,
            length=5,
            Uri="http://example.com/fig1.png",
            Description="Sample figure",
        ),
        # This figure won't appear since its id won't be matched.
        FigureHolder(
            FigureId="12345",
            offset=0,
            length=8,
            Uri="https://example.com/12345.png",
            Description="Figure 1",
        ),
    ]


# Test get_sections: It calls get_sections, then clean_sections internally.
def test_get_sections(cleaner, sample_text):
    sections = cleaner.get_sections(sample_text)
    # Expecting headers extracted and cleaned.
    assert sections == ["Header 1", "Header 2"]


# Test get_figure_ids: using regex extraction.
def test_get_figure_ids(cleaner, sample_text):
    figure_ids = cleaner.get_figure_ids(sample_text)
    assert figure_ids == ["12345"]


# Test clean_sections: Remove leading hashes and extra chars.
def test_clean_sections(cleaner):
    sections = ["### Section 1", "## Section 2"]
    cleaned = cleaner.clean_sections(sections)
    assert cleaned == ["Section 1", "Section 2"]


# Test remove_markdown_tags: Ensure tags are removed/replaced.
def test_remove_markdown_tags(cleaner):
    text = """
    <figure FigureId='12345'>Some figure</figure>
    <!-- FigureContent=Some content -->
    # Header
    Random sentence
    """
    tag_patterns = {
        "figurecontent": r"<!-- FigureContent=(.*?)-->",
        "figure": r"<figure(?:\s+FigureId=(\"[^\"]*\"|'[^']*'))?>(.*?)</figure>",
    }
    cleaned_text = cleaner.remove_markdown_tags(text, tag_patterns)
    # Check that the inner contents are retained but tags removed.
    assert "Some figure" in cleaned_text
    assert "Some content" in cleaned_text
    assert "<!-- FigureContent=Some content -->" not in cleaned_text
    assert "<figure FigureId='12345'>Some figure</figure>" not in cleaned_text


# Test clean_text_and_extract_metadata: Pass a ChunkHolder instance
def test_clean_text_and_extract_metadata(cleaner, sample_text, figures):
    # Create a ChunkHolder from the sample text.
    chunk = ChunkHolder(mark_up=sample_text)
    result = cleaner.clean_text_and_extract_metadata(chunk, figures)
    # result is a dict returned from model_dump (by alias)
    assert isinstance(result, dict)
    # The input text is stored under 'mark_up'
    assert result["mark_up"] == sample_text
    # get_sections should extract the headers.
    assert result["sections"] == ["Header 1", "Header 2"]
    # get_figure_ids returns ["12345"] so only the matching figure is kept.
    assert len(result["figures"]) == 1
    # FigureHolder uses alias "FigureId" for its id.
    assert result["figures"][0]["FigureId"] == "12345"
    # The cleaned text should have removed markup such as FigureId info.
    assert "FigureId='12345'" not in result["cleaned_text"]


# Async test for clean: using record dict with data holding a chunk sub-dict.
@pytest.mark.asyncio
async def test_clean(cleaner, sample_text):
    record = {
        "recordId": "1",
        "data": {
            "mark_up": sample_text,
            "figures": [
                {
                    "figure_id": "12345",
                    "uri": "https://example.com/12345.png",
                    "description": "Figure 1",
                    "offset": 0,
                    "length": 8,
                },
                {
                    "figure_id": "123456789",
                    "uri": "https://example.com/123456789.png",
                    "description": "Figure 2",
                    "offset": 10,
                    "length": 8,
                },
            ],
        },
    }
    result = await cleaner.clean(record)
    assert isinstance(result, dict)
    assert result["recordId"] == "1"
    # Ensure data was successfully cleaned
    assert result["data"] is not None
    assert result["data"]["cleaned_text"]
    # Check that the expected keys are in the cleaned data.
    assert "mark_up" in result["data"]
    assert "sections" in result["data"]
    assert "figures" in result["data"]
    # Only one figure must match because get_figure_ids extracted "12345"
    assert len(result["data"]["figures"]) == 1
    assert result["data"]["figures"][0]["FigureId"] == "12345"


# Test get_sections with empty text returns empty list.
def test_get_sections_empty_text(cleaner):
    sections = cleaner.get_sections("")
    assert sections == []


# Test get_figure_ids with no figure tags.
def test_get_figure_ids_no_figures(cleaner):
    text = "This text does not include any figures."
    assert cleaner.get_figure_ids(text) == []


# Test remove_markdown_tags with unknown tag patterns (should remain unchanged).
def test_remove_markdown_tags_unknown_tag(cleaner):
    text = "This is a basic text without markdown."
    tag_patterns = {"nonexistent": r"(pattern)"}
    result = cleaner.remove_markdown_tags(text, tag_patterns)
    assert result == text


# Test clean_text_and_extract_metadata with empty text: Should raise ValueError.
def test_clean_text_and_extract_metadata_empty_text(cleaner, figures):
    chunk = ChunkHolder(mark_up="")
    with pytest.raises(ValueError):
        cleaner.clean_text_and_extract_metadata(chunk, figures)


# Async test: missing "chunk" key in record -> error branch of clean().
@pytest.mark.asyncio
async def test_clean_missing_chunk(cleaner):
    record = {
        "recordId": "3",
        "data": {"figures": []},
    }
    result = await cleaner.clean(record)
    assert result["recordId"] == "3"
    assert result["data"] is None
    assert result["errors"] is not None
    assert "Failed to cleanup data" in result["errors"][0]["message"]


# Async test: invalid figure structure causing an exception in clean()
@pytest.mark.asyncio
async def test_clean_with_invalid_figures_structure(cleaner):
    record = {
        "recordId": "4",
        "data": {
            "chunk": {"mark_up": "Some text with # Header"},
            # Figures missing required keys for FigureHolder.
            "figures": [{"invalid_key": "no_fig_id"}],
        },
    }
    result = await cleaner.clean(record)
    assert result["recordId"] == "4"
    assert result["data"] is None
    assert result["errors"] is not None


def test_clean_only_figures_sets_page_number(cleaner):
    # Input contains only a figure tag.
    text = "<figure FigureId='12345'>I am a random description</figure>"
    chunk = ChunkHolder(mark_up=text, page_number=1)
    figs = [
        FigureHolder(
            FigureId="12345",
            offset=0,
            length=10,
            Uri="http://example.com/12345.png",
            Description="Figure 1",
            page_number=2,  # This page number should be picked up.
        ),
        FigureHolder(
            FigureId="67890",
            offset=20,
            length=10,
            Uri="http://example.com/67890.png",
            Description="Figure 2",
            page_number=4,
        ),
    ]
    result = cleaner.clean_text_and_extract_metadata(chunk, figs)
    # Because no text outside the figure tag is present, sections should be empty,
    # and page_number should be set from the first matching figure.
    assert result.get("sections") == []
    assert result["page_number"] == 2


def test_clean_text_with_mixed_content_leaves_page_number_unset(cleaner):
    # Input contains text outside of the figure tag.
    # Even though a figure appears, the presence of other text means page_number should not be auto-set as the chunk could overlap pages.
    text = "More text before the figure. <figure FigureId='12345'></figure>"
    chunk = ChunkHolder(mark_up=text, page_number=4)
    figs = [
        FigureHolder(
            FigureId="12345",
            offset=0,
            length=10,
            Uri="http://example.com/12345.png",
            Description="Figure 1",
            page_number=5,  # This should be ignored since text exists.
        )
    ]
    result = cleaner.clean_text_and_extract_metadata(chunk, figs)
    assert result.get("page_number") == 4
