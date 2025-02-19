# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


import pytest
from mark_up_cleaner import MarkUpCleaner
from layout_holders import FigureHolder


@pytest.fixture
def cleaner():
    return MarkUpCleaner()


@pytest.fixture
def sample_text():
    return """
    # Header 1\n
    Some text.\n
    ## Header 2\n
    More text.\n
    <figure FigureId='12345'></figure>
    """


@pytest.fixture
def figures():
    return [
        FigureHolder(
            figure_id="12345",
            description="Figure 1",
            uri="https://example.com/12345.png",
            offset=0,
            length=8,
        )
    ]


def test_get_sections(cleaner, sample_text):
    sections = cleaner.get_sections(sample_text)
    assert sections == ["Header 1", "Header 2"]


def test_get_figure_ids(cleaner, sample_text):
    figure_ids = cleaner.get_figure_ids(sample_text)
    assert figure_ids == ["12345"]


def test_clean_sections(cleaner):
    sections = ["### Section 1", "## Section 2"]
    cleaned = cleaner.clean_sections(sections)
    assert cleaned == ["Section 1", "Section 2"]


def test_remove_markdown_tags(cleaner):
    text = """
    <figure FigureId='12345'>Some figure</figure>
    <!-- FigureContent=Some content -->
    # Header
    Random sentence
    """
    tag_patterns = {
        "figurecontent": r"<!-- FigureContent=(.*?)-->",
        "figure": r"<figure(?:\s+FigureId=\"[^\"]*\")?>(.*?)</figure>",
    }
    cleaned_text = cleaner.remove_markdown_tags(text, tag_patterns)
    assert "Some figure" in cleaned_text
    assert "Some content" in cleaned_text
    assert "<!-- FigureContent=Some content -->" not in cleaned_text
    assert "<figure FigureId='12345'>Some figure</figure>" not in cleaned_text


def test_clean_text_and_extract_metadata(cleaner, sample_text, figures):
    result = cleaner.clean_text_and_extract_metadata(sample_text, figures)
    assert isinstance(result, dict)
    assert result["chunk_mark_up"] == sample_text
    assert result["chunk_sections"] == ["Header 1", "Header 2"]
    assert result["chunk_figures"] == [
        {
            "figure_id": "12345",
            "uri": "https://example.com/12345.png",
            "description": "Figure 1",
        }
    ]
    assert "chunk_cleaned" in result
    assert "FigureId='12345'" not in result["chunk_cleaned"]


@pytest.mark.asyncio
async def test_clean(cleaner, sample_text, figures):
    record = {
        "recordId": "1",
        "data": {
            "chunk": sample_text,
            "figures": [
                {
                    "figure_id": "12345",
                    "uri": "https://example.com/12345.png",
                    "description": "Figure 1",
                },
                {
                    "figure_id": "123456789",
                    "uri": "https://example.com/123456789.png",
                    "description": "Figure 2",
                },
            ],
        },
    }
    result = await cleaner.clean(record)
    assert isinstance(result, dict)
    assert result["recordId"] == "1"
    assert result["data"] is not None
    assert result["data"]["chunk_cleaned"]
    assert "errors" not in result or result["errors"] is None
