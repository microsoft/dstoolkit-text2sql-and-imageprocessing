# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class FigureHolder(BaseModel):
    """A class to hold the figure extracted from the document."""

    figure_id: str = Field(..., alias="FigureId")
    container: Optional[str] = Field(exclude=True, default=None)
    blob: Optional[str] = Field(exclude=True, default=None)
    caption: Optional[str] = Field(default=None, alias="Caption")
    offset: int
    length: int
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    uri: str = Field(..., alias="Uri")
    description: Optional[str] = Field(default="", alias="Description")
    data: Optional[str] = Field(default=None, alias="Data")

    model_config = ConfigDict(populate_by_name=True)

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


class PageNumberTrackingHolder(BaseModel):
    """A class to hold the starting sentence of each page."""

    page_number: int
    page_content: str | None


class NonPageWiseContentHolder(BaseModel):
    """A class to hold the non-page-wise content extracted from the document."""

    layout: LayoutHolder
    page_number_tracking_holders: list[PageNumberTrackingHolder] = Field(
        default_factory=list
    )


class ChunkHolder(BaseModel):
    """A class to hold the text extracted from the document after it has been chunked."""

    mark_up: str
    sections: Optional[list[str]] = Field(default_factory=list)
    figures: Optional[list[FigureHolder]] = Field(default_factory=list)
    cleaned_text: Optional[str] = None
    page_number: Optional[int] = Field(default=None)
