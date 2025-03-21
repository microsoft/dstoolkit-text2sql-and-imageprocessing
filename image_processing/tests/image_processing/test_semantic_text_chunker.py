# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest
from unittest.mock import AsyncMock, MagicMock

from semantic_text_chunker import (
    process_semantic_text_chunker,
    SemanticTextChunker,
)

from layout_holders import ChunkHolder, PageNumberTrackingHolder

# --- Dummy Classes for Process-Level Tests ---


class DummyChunkHolder:
    def __init__(self, mark_up, page_number=None):
        self.mark_up = mark_up
        self.page_number = page_number

    def model_dump(self, by_alias=False):
        return {"mark_up": self.mark_up, "page_number": self.page_number}


class DummyPageNumberTrackingHolder:
    def __init__(self, page_content, page_number):
        self.page_content = page_content
        self.page_number = page_number


# --- Process-Level Tests (Using Dummy Chunker) ---


@pytest.mark.parametrize(
    "chunk_contents, page_content, expected_page",
    [
        # Test matching on markdown heading
        (["# Title", "Content"], "# Title", 2),
        # Test matching on newline content
        (["First line", "Second line"], "First line", 3),
        # Test matching on period
        (["First sentence. Second sentence"], "First sentence. Second sentence", 4),
        # Test matching on table
        (["<table>Table content</table>"], "", 1),
        # Test no match (should get default page 1)
        (["Content not in any page_content"], "Different content", 1),
    ],
)
def test_assign_page_number_to_chunks(chunk_contents, page_content, expected_page):
    """Test the page assignment logic for different types of content."""
    # Create a real SemanticTextChunker instance
    chunker = SemanticTextChunker()

    chunks = [ChunkHolder(mark_up=chunk_content) for chunk_content in chunk_contents]

    # Create chunks with different content types

    # Create page tracking holders
    page_tracking_holders = [
        PageNumberTrackingHolder(page_content="", page_number=1),
        PageNumberTrackingHolder(page_content="# Title", page_number=2),
        PageNumberTrackingHolder(page_content="First line", page_number=3),
        PageNumberTrackingHolder(page_content="First sentence", page_number=4),
        PageNumberTrackingHolder(page_content="Different content", page_number=5),
    ]

    # Call the method being tested
    result_chunks = chunker.assign_page_number_to_chunks(chunks, page_tracking_holders)

    # Verify the page number was correctly assigned
    assert result_chunks[0].page_number == expected_page


def test_assign_page_number_to_chunks_multiple_chunks():
    """Test assigning page numbers to multiple chunks."""
    chunker = SemanticTextChunker()

    # Create multiple chunks
    chunks = [
        ChunkHolder(mark_up="# Introduction\nThis is the first section."),
        ChunkHolder(mark_up="# Methods\nThis describes the methods used."),
        ChunkHolder(mark_up="# Results\nThese are the results."),
    ]

    # Create page tracking holders for different sections
    page_tracking_holders = [
        PageNumberTrackingHolder(page_content="# Introduction", page_number=1),
        PageNumberTrackingHolder(page_content="# Methods", page_number=3),
        PageNumberTrackingHolder(page_content="# Results", page_number=5),
    ]

    # Call the method being tested
    result_chunks = chunker.assign_page_number_to_chunks(chunks, page_tracking_holders)

    # Verify page numbers were correctly assigned
    assert result_chunks[0].page_number == 1
    assert result_chunks[1].page_number == 3
    assert result_chunks[2].page_number == 5


@pytest.mark.asyncio
async def test_process_semantic_text_chunker_failure():
    """Test that an exception during chunking is caught and returns an error record."""
    record = {
        "recordId": "3",
        "data": {"content": "Content that will trigger an error."},
    }

    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(side_effect=Exception("Chunking error"))
    dummy_text_chunker.assign_page_number_to_chunks = MagicMock()

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "3"
    assert result["data"] is None
    assert "errors" in result
    assert isinstance(result["errors"], list)
    assert result["errors"][0]["message"].startswith("Failed to chunk data")


@pytest.mark.asyncio
async def test_process_semantic_text_chunker_multiple_chunks():
    """
    Test a record where chunk() returns multiple chunks and per-page starting sentences
    assign different page numbers to different chunks.
    """
    record = {
        "recordId": "4",
        "data": {
            "content": "Content that generates multiple chunks.",
            "page_number_tracking_holders": [
                {"page_content": "first_page", "page_number": 3},
                {"page_content": "second_page", "page_number": 4},
            ],
        },
    }

    dummy_chunk1 = DummyChunkHolder("This chunk contains first_page indicator")
    dummy_chunk2 = DummyChunkHolder("This chunk contains second_page indicator")
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(return_value=[dummy_chunk1, dummy_chunk2])

    def dummy_assign_page(chunks, page_number_tracking_holders):
        ps_objs = [
            DummyPageNumberTrackingHolder(**ps.__dict__)
            for ps in page_number_tracking_holders
        ]
        page_number = 1
        for chunk in chunks:
            for ps in ps_objs:
                if ps.page_content in chunk.mark_up:
                    page_number = ps.page_number
                    break
            chunk.page_number = page_number
        return chunks

    dummy_text_chunker.assign_page_number_to_chunks = dummy_assign_page

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "4"
    chunks = result["data"]["chunks"]
    assert isinstance(chunks, list)
    assert len(chunks) == 2
    assert chunks[0]["page_number"] == 3
    assert chunks[1]["page_number"] == 4


@pytest.mark.asyncio
async def test_process_semantic_text_chunker_empty_content():
    """
    Test that if the content is empty and chunk() raises a ValueError (e.g. because no chunks were generated),
    the error is handled and an error record is returned.
    """
    record = {"recordId": "7", "data": {"content": ""}}
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(
        side_effect=ValueError("No chunks were generated")
    )
    dummy_text_chunker.assign_page_number_to_chunks = MagicMock()

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "7"
    assert result["data"] is None
    assert "errors" in result
    assert isinstance(result["errors"], list)
    assert result["errors"][0]["message"].startswith("Failed to chunk data")


# --- Helper Classes for Chunk Splitting Tests ---


# A simple dummy spaCy-like model for sentence segmentation.
class DummySpan:
    def __init__(self, text):
        self.text = text


class DummyDoc:
    def __init__(self, text):
        # Naively split on period.
        # (Ensure test texts include periods as sentence delimiters.)
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        self.sents = [DummySpan(s) for s in sentences]


class DummyNLP:
    def __call__(self, text, disable):
        return DummyDoc(text)


# Fixture that returns a SemanticTextChunker instance with patched components.
@pytest.fixture
def chunker():
    # Use relaxed thresholds so that even short sentences qualify.
    stc = SemanticTextChunker(
        similarity_threshold=0.8,
        max_chunk_tokens=1000,
        min_chunk_tokens=1,
    )
    # Override the spaCy model with our dummy.
    stc._nlp_model = DummyNLP()
    # Override token counting to simply count words.
    stc.num_tokens_from_string = lambda s: len(s.split())
    # For these tests, assume all sentences are very similar (so merge_similar_chunks doesn’t force a split).
    stc.sentence_similarity = lambda a, b: 1.0
    return stc


@pytest.mark.asyncio
async def test_chunk_markdown_heading(chunker):
    """
    Test that a markdown heading is padded with newlines.
    """
    text = "Introduction. # Heading. More text."
    chunks = await chunker.chunk(text)
    # The heading should have been transformed to include "\n\n" before and after.
    # Because merge_chunks may merge sentences, check that the final text contains the padded heading.
    combined = " ".join(chunk.mark_up for chunk in chunks)
    assert "\n\n# Heading\n\n" in combined


@pytest.mark.asyncio
async def test_chunk_table(chunker):
    """
    Test that a complete table element is detected.
    """
    text = "Before table. <table>Table content</table>. After table."
    chunks = await chunker.chunk(text)
    # Expect at least one chunk containing a complete table.
    table_chunks = [
        c.mark_up for c in chunks if "<table" in c.mark_up and "</table>" in c.mark_up
    ]
    assert len(table_chunks) >= 1


@pytest.mark.asyncio
async def test_chunk_long_sentence():
    """
    Test that a sentence with many words (exceeding max_chunk_tokens) is immediately emitted as a chunk.
    """
    # Create a chunker that forces a long sentence to exceed the max token threshold.
    stc = SemanticTextChunker(
        similarity_threshold=0.8,
        max_chunk_tokens=5,  # set low so even a few words exceed it
        min_chunk_tokens=1,
    )
    stc._nlp_model = DummyNLP()
    stc.num_tokens_from_string = lambda s: len(s.split())
    stc.sentence_similarity = lambda a, b: 1.0
    # This sentence has 12 words.
    text = "This sentence has many words that exceed the maximum chunk token limit."
    chunks = await stc.chunk(text)
    # Since our dummy NLP splits on period, we expect one sentence.
    # And because 12 >= 5, that sentence is immediately appended as a chunk.
    assert len(chunks) == 1
    assert "exceed" in chunks[0].mark_up


def test_assign_page_number_with_html_comments():
    """Test that HTML comments are properly stripped when assigning page numbers."""
    chunker = SemanticTextChunker()

    # Create a chunk with HTML comments
    chunk = ChunkHolder(mark_up="<!-- comment --> First line\nSecond line")

    # Create page tracking holders
    page_tracking_holders = [
        PageNumberTrackingHolder(page_content="First line\nSecond line", page_number=3),
    ]

    # Call the method being tested
    result_chunks = chunker.assign_page_number_to_chunks([chunk], page_tracking_holders)

    # Verify the page number was correctly assigned despite the HTML comment
    assert result_chunks[0].page_number == 3


@pytest.mark.asyncio
async def test_clean_new_lines():
    """Test the clean_new_lines method properly processes newlines."""
    chunker = SemanticTextChunker()

    # Test with various newline patterns
    text = "<p>First line\nSecond line</p>\n\n<p>Next paragraph</p>"
    result = chunker.clean_new_lines(text)

    # Check that single newlines between tags are removed
    assert "<p>First line Second line</p>" in result
    # Check that multiple newlines are replaced with space + \n\n
    assert "</p> \n\n<p>" in result


@pytest.mark.asyncio
async def test_filter_empty_figures():
    """Test the filter_empty_figures method removes empty figure tags."""
    chunker = SemanticTextChunker()

    # Test with empty and non-empty figures
    text = "<p>Text</p><figure></figure><p>More text</p><figure>Content</figure>"
    result = chunker.filter_empty_figures(text)

    # Check that empty figures are removed
    assert "<figure></figure>" not in result
    # Check that non-empty figures remain
    assert "<figure>Content</figure>" in result


@pytest.mark.asyncio
async def test_group_figures_and_tables():
    """Test grouping of figures and tables into sentences."""
    chunker = SemanticTextChunker()

    sentences = ["Before table.", "<table>Row 1", "Row 2</table>", "After table."]

    grouped, is_table_map = chunker.group_figures_and_tables_into_sentences(sentences)

    # Check that table contents are grouped
    assert len(grouped) == 3
    assert "<table>Row 1 Row 2</table>" in grouped
    # Check table map is correct
    assert is_table_map == [False, True, False]


@pytest.mark.asyncio
async def test_remove_figures():
    """Test the remove_figures method."""
    chunker = SemanticTextChunker()

    text = 'Text before <figure FigureId="fig1">Figure content</figure> text after'
    result = chunker.remove_figures(text)

    assert "Text before  text after" == result
    assert "<figure" not in result


@pytest.mark.asyncio
async def test_complex_document_structure():
    """Test chunking with mixed content types (headings, lists, tables)."""
    chunker = SemanticTextChunker()

    text = """# Heading 1

Some paragraph text.

## Heading 2
- List item 1
- List item 2

<table>
<tr><td>Cell 1</td><td>Cell 2</td></tr>
</table>

> Blockquote text"""

    chunks = await chunker.chunk(text)

    # Verify we have reasonable chunks
    assert len(chunks) >= 1

    # Check heading formatting
    heading_chunks = [c for c in chunks if "# Heading 1" in c.mark_up]
    assert len(heading_chunks) > 0
    assert "# Heading" in heading_chunks[0].mark_up


@pytest.mark.asyncio
async def test_process_page_tracking_no_match():
    """Test behavior when page_number_tracking_holders is provided but doesn't match any chunks."""
    record = {
        "recordId": "8",
        "data": {
            "content": "Unique content that won't match page tracking.",
            "page_number_tracking_holders": [
                {"page_content": "Something completely different", "page_number": 10}
            ],
        },
    }

    chunker = SemanticTextChunker()
    result = await process_semantic_text_chunker(record, chunker)

    # Should default to page 1 when no match is found
    assert result["data"]["chunks"][0]["page_number"] == 1


@pytest.mark.asyncio
async def test_nested_html_structure():
    """Test handling of nested HTML tags."""
    chunker = SemanticTextChunker()

    text = """<div>
        <p>Paragraph with <strong>bold text</strong> and <em>italic text</em></p>
        <table>
            <tr><th>Header 1</th><th>Header 2</th></tr>
            <tr><td>Value 1</td><td>Value 2</td></tr>
        </table>
    </div>"""

    chunks = await chunker.chunk(text)

    # Verify we get at least one chunk
    assert len(chunks) > 0
    # Check that the table is kept intact in one chunk
    table_chunks = [
        c for c in chunks if "<table>" in c.mark_up and "</table>" in c.mark_up
    ]
    assert len(table_chunks) > 0


def test_sentence_similarity():
    """Test the sentence_similarity method."""
    chunker = SemanticTextChunker()

    # Should be highly similar
    text1 = "Machine learning is a field of artificial intelligence."
    text2 = "Artificial intelligence includes the domain of machine learning."
    similarity = chunker.sentence_similarity(text1, text2)

    # The exact value will depend on the model, but should be relatively high
    assert similarity > 0.5

    # Should be less similar
    text3 = "Python is a programming language."
    similarity2 = chunker.sentence_similarity(text1, text3)

    # Should be lower than the first comparison
    assert similarity2 < similarity


@pytest.mark.asyncio
async def test_special_characters_handling():
    """Test chunking text with special characters and non-English content."""
    chunker = SemanticTextChunker()

    text = """# Résumé

Special characters: ©®™℠

Non-English: こんにちは 你好 안녕하세요

Math symbols: ∑ ∫ ∏ √ ∂ Δ π μ σ"""

    chunks = await chunker.chunk(text)

    # Verify chunks were created
    assert len(chunks) > 0
    # Check content is preserved
    combined_content = " ".join(c.mark_up for c in chunks)
    assert "©®™℠" in combined_content
    assert "こんにちは" in combined_content
