import pytest
from unittest.mock import AsyncMock, MagicMock

from semantic_text_chunker import (
    process_semantic_text_chunker,
    SemanticTextChunker,
)

# --- Dummy Classes for Process-Level Tests ---


class DummyChunkHolder:
    def __init__(self, mark_up, page_number=None):
        self.mark_up = mark_up
        self.page_number = page_number

    def model_dump(self, by_alias=False):
        return {"mark_up": self.mark_up, "page_number": self.page_number}


class DummyPerPageStartingSentenceHolder:
    def __init__(self, starting_sentence, page_number):
        self.starting_sentence = starting_sentence
        self.page_number = page_number


# --- Process-Level Tests (Using Dummy Chunker) ---


@pytest.mark.asyncio
async def test_process_semantic_text_chunker_success_without_page():
    """Test a successful chunking when no per-page starting sentences are provided."""
    record = {"recordId": "1", "data": {"content": "Some content to be chunked."}}

    dummy_chunk = DummyChunkHolder("chunk1")
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(return_value=[dummy_chunk])
    dummy_text_chunker.assign_page_number_to_chunks = MagicMock()

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "1"
    assert result["data"] is not None
    chunks = result["data"]["chunks"]
    assert isinstance(chunks, list)
    assert len(chunks) == 1
    assert chunks[0]["mark_up"] == "chunk1"
    # When no page info is provided, page_number remains unchanged (None in our dummy).
    assert chunks[0]["page_number"] is None


@pytest.mark.asyncio
async def test_process_semantic_text_chunker_success_with_page():
    """Test a successful chunking when per-page starting sentences are provided and match a chunk."""
    record = {
        "recordId": "2",
        "data": {
            "content": "Some content to be chunked.",
            "per_page_starting_sentences": [
                {"starting_sentence": "chunk", "page_number": 5}
            ],
        },
    }

    dummy_chunk = DummyChunkHolder("This dummy chunk contains chunk in its text")
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(return_value=[dummy_chunk])

    def dummy_assign_page(chunks, per_page_starting_sentences):
        ps_objs = [
            DummyPerPageStartingSentenceHolder(**ps.__dict__)
            for ps in per_page_starting_sentences
        ]
        page_number = 1
        for chunk in chunks:
            for ps in ps_objs:
                if ps.starting_sentence in chunk.mark_up:
                    page_number = ps.page_number
                    break
            chunk.page_number = page_number
        return chunks

    dummy_text_chunker.assign_page_number_to_chunks = dummy_assign_page

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "2"
    chunks = result["data"]["chunks"]
    assert isinstance(chunks, list)
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 5


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
            "per_page_starting_sentences": [
                {"starting_sentence": "first_page", "page_number": 3},
                {"starting_sentence": "second_page", "page_number": 4},
            ],
        },
    }

    dummy_chunk1 = DummyChunkHolder("This chunk contains first_page indicator")
    dummy_chunk2 = DummyChunkHolder("This chunk contains second_page indicator")
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(return_value=[dummy_chunk1, dummy_chunk2])

    def dummy_assign_page(chunks, per_page_starting_sentences):
        ps_objs = [
            DummyPerPageStartingSentenceHolder(**ps.__dict__)
            for ps in per_page_starting_sentences
        ]
        page_number = 1
        for chunk in chunks:
            for ps in ps_objs:
                if ps.starting_sentence in chunk.mark_up:
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
async def test_process_semantic_text_chunker_empty_page_sentences():
    """
    Test a record where 'per_page_starting_sentences' exists but is empty.
    In this case, the default page (1) is assigned.
    """
    record = {
        "recordId": "5",
        "data": {
            "content": "Some content to be chunked.",
            "per_page_starting_sentences": [],
        },
    }

    dummy_chunk = DummyChunkHolder("Chunk without any page indicator")
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(return_value=[dummy_chunk])

    def dummy_assign_page(chunks, per_page_starting_sentences):
        for chunk in chunks:
            chunk.page_number = 1
        return chunks

    dummy_text_chunker.assign_page_number_to_chunks = dummy_assign_page

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "5"
    chunks = result["data"]["chunks"]
    assert isinstance(chunks, list)
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 1


@pytest.mark.asyncio
async def test_process_semantic_text_chunker_missing_data():
    """
    Test that if the record is missing the 'data' key, the function returns an error.
    """
    record = {"recordId": "6"}
    dummy_text_chunker = MagicMock()
    dummy_text_chunker.chunk = AsyncMock(return_value=[DummyChunkHolder("chunk")])
    dummy_text_chunker.assign_page_number_to_chunks = MagicMock()

    result = await process_semantic_text_chunker(record, dummy_text_chunker)
    assert result["recordId"] == "6"
    assert result["data"] is None
    assert "errors" in result


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
    def __call__(self, text):
        return DummyDoc(text)


# Fixture that returns a SemanticTextChunker instance with patched components.
@pytest.fixture
def chunker():
    # Use relaxed thresholds so that even short sentences qualify.
    stc = SemanticTextChunker(
        num_surrounding_sentences=1,
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


# --- Chunk Splitting Tests Using Real (Patched) Chunker ---


@pytest.mark.asyncio
async def test_chunk_complete_figure(chunker):
    """
    Test a text containing a complete <figure> element.
    Expect that the sentence with the complete figure is detected and grouped.
    """
    text = "Text before. <figure>Figure content</figure>. Text after."
    chunks = await chunker.chunk(text)
    # For our dummy segmentation, we expect two final chunks:
    # one that combines "Text before" and the figure, and one for "Text after".
    assert len(chunks) == 2
    # Check that the first chunk contains a complete figure.
    assert "<figure" in chunks[0].mark_up
    assert "</figure>" in chunks[0].mark_up


@pytest.mark.asyncio
async def test_chunk_incomplete_figure(chunker):
    """
    Test a text with an incomplete figure element spanning multiple sentences.
    The start and end of the figure should be grouped together.
    """
    text = (
        "Text before. <figure>Start of figure. Figure continues </figure>. Text after."
    )
    chunks = await chunker.chunk(text)
    # Expected grouping: one chunk combining the normal text and the grouped figure,
    # and another chunk for text after.
    assert len(chunks) == 2
    # Check that the grouped chunk contains both the start and the end of the figure.
    assert "<figure" in chunks[0].mark_up
    assert "</figure>" in chunks[0].mark_up


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
        num_surrounding_sentences=1,
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
