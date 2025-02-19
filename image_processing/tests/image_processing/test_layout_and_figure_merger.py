# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest
from layout_holders import LayoutHolder, FigureHolder
from layout_and_figure_merger import LayoutAndFigureMerger


@pytest.fixture
def layout_holder():
    return LayoutHolder(
        content="This is a sample layout with a figure placeholder.<figure></figure> This is a sentence after."
    )


@pytest.fixture
def figure_holder():
    return FigureHolder(
        figure_id="12345",
        description="Figure 1",
        uri="https://example.com/12345.png",
        offset=50,
        length=17,
    )


@pytest.fixture
def merger():
    return LayoutAndFigureMerger()


def test_insert_figure_description(merger, layout_holder, figure_holder):
    updated_layout, inserted_length = merger.insert_figure_description(
        layout_holder, figure_holder
    )
    assert "<figure FigureId='12345'>Figure 1</figure>" in updated_layout.content
    assert (
        inserted_length
        == len("<figure FigureId='12345'>Figure 1</figure>") - figure_holder.length
    )
    assert (
        updated_layout.content
        == "This is a sample layout with a figure placeholder.<figure FigureId='12345'>Figure 1</figure> This is a sentence after."
    )


def test_insert_figure_invalid_offset(merger, layout_holder):
    invalid_figure = FigureHolder(
        figure_id="12345",
        offset=100,
        length=5,
        description="Invalid figure",
        uri="https://example.com/12345.png",
    )
    with pytest.raises(ValueError, match="Figure offset is out of bounds"):
        merger.insert_figure_description(layout_holder, invalid_figure)


@pytest.mark.asyncio
async def test_merge_figures_into_layout(merger, layout_holder, figure_holder):
    figures = [figure_holder]
    updated_layout = await merger.merge_figures_into_layout(layout_holder, figures)
    assert "<figure FigureId='12345'>Figure 1</figure>" in updated_layout.content
    assert (
        updated_layout.content
        == "This is a sample layout with a figure placeholder.<figure FigureId='12345'>Figure 1</figure> This is a sentence after."
    )


@pytest.mark.asyncio
async def test_merge_removes_irrelevant_figures(merger):
    layout_holder = LayoutHolder(
        content="Before <figure>'Irrelevant Image'</figure> After"
    )
    updated_layout = await merger.merge_figures_into_layout(layout_holder, [])
    assert "Irrelevant Image" not in updated_layout.content
    assert "Before  After" in updated_layout.content


@pytest.mark.asyncio
async def test_merge_removes_empty_figures(merger):
    layout_holder = LayoutHolder(content="Before <figure> </figure> After")
    updated_layout = await merger.merge_figures_into_layout(layout_holder, [])
    assert "<figure> </figure>" not in updated_layout.content
    assert "Before  After" in updated_layout.content


@pytest.mark.asyncio
async def test_merge_removes_html_comments(merger):
    layout_holder = LayoutHolder(content="Before <!-- Comment --> After")
    updated_layout = await merger.merge_figures_into_layout(layout_holder, [])
    assert "<!-- Comment -->" not in updated_layout.content
    assert "Before  After" in updated_layout.content


@pytest.mark.asyncio
async def test_merge_handles_exception(merger):
    record = {
        "recordId": "1",
        "data": {
            "layout": {"content": "Sample"},
            "figures": [
                {
                    "figure_id": "12345",
                    "offset": 1000,
                    "length": 5,
                    "description": "Invalid",
                    "uri": "https://example.com/12345.png",
                }
            ],
        },
    }
    response = await merger.merge(record)
    assert response["data"] is None
    assert response["errors"] is not None
