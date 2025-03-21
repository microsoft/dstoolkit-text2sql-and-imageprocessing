# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest
from pydantic import ValidationError
from layout_holders import (
    FigureHolder,
    LayoutHolder,
    PageWiseContentHolder,
    NonPageWiseContentHolder,
    ChunkHolder,
    PageNumberTrackingHolder,
)


def test_figure_holder_creation():
    figure = FigureHolder(
        FigureId="fig1",
        offset=10,
        length=5,
        Uri="http://example.com/fig1.png",
        Description="Sample figure",
    )

    assert figure.figure_id == "fig1"
    assert figure.offset == 10
    assert figure.length == 5
    assert figure.uri == "http://example.com/fig1.png"
    assert figure.description == "Sample figure"
    assert figure.markdown == "<figure FigureId='fig1'>Sample figure</figure>"


def test_figure_holder_missing_required_fields():
    with pytest.raises(ValidationError):
        FigureHolder(offset=10, length=5, Uri="http://example.com/fig1.png")


def test_layout_holder_creation():
    layout = LayoutHolder(content="Sample content")
    assert layout.content == "Sample content"
    assert layout.page_number is None
    assert layout.page_offsets == 0
    assert layout.figures == []


def test_layout_holder_with_figures():
    figure = FigureHolder(
        FigureId="fig1",
        offset=10,
        length=5,
        Uri="http://example.com/fig1.png",
        Description="Sample figure",
    )
    layout = LayoutHolder(content="Sample content", figures=[figure])
    assert len(layout.figures) == 1
    assert layout.figures[0].figure_id == "fig1"


def test_page_wise_content_holder():
    layout1 = LayoutHolder(content="Page 1")
    layout2 = LayoutHolder(content="Page 2")
    page_holder = PageWiseContentHolder(page_wise_layout=[layout1, layout2])
    assert len(page_holder.page_wise_layout) == 2
    assert page_holder.page_wise_layout[0].content == "Page 1"


def test_non_page_wise_content_holder():
    layout = LayoutHolder(content="Full document")
    non_page_holder = NonPageWiseContentHolder(layout=layout)
    assert non_page_holder.layout.content == "Full document"


def test_chunk_holder_creation():
    chunk = ChunkHolder(
        mark_up="Sample markup",
        sections=["Section1", "Section2"],
        figures=[],
        cleaned_text="Cleaned text content",
        page_number=1,
    )
    assert chunk.mark_up == "Sample markup"
    assert chunk.sections == ["Section1", "Section2"]
    assert chunk.cleaned_text == "Cleaned text content"
    assert chunk.page_number == 1


def test_per_page_page_content_holder_creation():
    sentence = PageNumberTrackingHolder(
        page_number=1, page_content="This is the full content."
    )
    assert sentence.page_number == 1
    assert sentence.page_content == "This is the full content."


def test_non_page_wise_content_holder_with_page_number_trackers():
    layout = LayoutHolder(content="Full document")
    page_number_trackers = [
        PageNumberTrackingHolder(page_number=1, page_content="Start 1"),
        PageNumberTrackingHolder(page_number=2, page_content="Start 2"),
    ]
    non_page_holder = NonPageWiseContentHolder(
        layout=layout, page_number_tracking_holders=page_number_trackers
    )
    assert non_page_holder.layout.content == "Full document"
    assert len(non_page_holder.page_number_tracking_holders) == 2
    assert non_page_holder.page_number_tracking_holders[0].page_content == "Start 1"
