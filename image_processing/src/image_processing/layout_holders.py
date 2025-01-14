# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from pydantic import BaseModel, Field
from typing import Optional


class FigureHolder(BaseModel):

    """A class to hold the figure extracted from the document."""

    figure_id: str
    container: str = Field(exclude=True)
    blob: str = Field(exclude=True)
    caption: Optional[str] = Field(default=None)
    offset: int
    length: int
    page_number: Optional[int] = Field(default=None)
    uri: str
    description: Optional[str] = Field(default="")
    data: Optional[str] = Field(default=None)

    @property
    def markdown(self) -> str:
        """Convert the figure to a Markdown string.

        Returns:
        --------
            str: The Markdown string representation of the figure."""

        return f"<figure FigureId='{self.figure_id}'>{self.description}</figure>"


class LayoutHolder(BaseModel):
    """A class to hold the text extracted from the document."""

    content: str
    page_number: Optional[int] = None
    page_offsets: Optional[int] = 0
    figures: list[FigureHolder] = Field(default_factory=list)


class PageWiseContentHolder(BaseModel):
    """A class to hold the page-wise content extracted from the document."""

    page_wise_layout: list[LayoutHolder]


class NonPageWiseContentHolder(BaseModel):
    """A class to hold the non-page-wise content extracted from the document."""

    layout: LayoutHolder
