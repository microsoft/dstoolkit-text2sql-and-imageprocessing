# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import re
from layout_holders import FigureHolder, LayoutHolder


class LayoutAndFigureMerger:
    def insert_figure_description(
        self, layout_holder: LayoutHolder, figure_holder: FigureHolder
    ) -> int:
        """
        Updates the figure description in the Markdown content.

        Args:
            layout_holder (LayoutHolder): The layout text.
            figure_holder (FigureHolder): The figure to be updated.

        Returns:
            str: The updated Markdown content with the new figure description.
        """

        # Calculate the end index of the content to be replaced
        end_index = figure_holder.offset + figure_holder.length

        # Ensure that the end_index does not exceed the length of the Markdown content
        if end_index > len(layout_holder.content):
            logging.info(
                "End index exceeds the length of the content. Adjusting the end index to the length of the content."
            )
            end_index = len(layout_holder.content)

        # Replace the old string with the new string
        layout_holder.content = (
            layout_holder.content[: figure_holder.offset]
            + figure_holder.markdown
            + layout_holder.content[end_index:]
        )

        return len(figure_holder.markdown) - figure_holder.length

    async def merge_figures_into_layout(
        self, layout: LayoutHolder, figures: list[FigureHolder]
    ) -> LayoutHolder:
        """
        Merges the figures into the layout.

        Args:
            layout (LayoutHolder): The layout text.
            figures (list): The list of figures.

        Returns:
            LayoutHolder: The updated layout text with the figures.
        """
        # Initialize the offset
        running_offset = 0

        # Iterate over the figures
        for figure in figures:
            logging.info(f"Inserting Figure: {figure.figure_id}")
            # Update the figure description in the layout
            figure.offset += running_offset
            length = self.insert_figure_description(layout, figure)

            # Update the offset
            running_offset += length

        # Remove irrelevant figures
        irrelevant_figure_pattern = r"<figure[^>]*>.*?Irrelevant Image.*?</figure>"
        layout.content = re.sub(
            irrelevant_figure_pattern, "", layout.content, flags=re.DOTALL
        )

        empty_or_whitespace_figure_pattern = r"<figure[^>]*>\s*</figure>"
        layout.content = re.sub(
            empty_or_whitespace_figure_pattern, "", layout.content, flags=re.DOTALL
        )

        html_comments_pattern = r"<!--.*?-->"
        layout.content = re.sub(
            html_comments_pattern, "", layout.content, flags=re.DOTALL
        )

        return layout

    async def merge(self, record: dict) -> dict:
        """
        Analyse the image and generate a description for it.

        Parameters:
        - record (dict): The record containing the image and its caption.

        Returns:
        - record (dict): The record containing the image, its caption, and the generated description.
        """
        layout = LayoutHolder(**record["data"]["layout"])

        figures = [FigureHolder(**figure) for figure in record["data"]["figures"]]

        try:
            logging.info(f"Input Data: {layout}")
            updated_layout = await self.merge_figures_into_layout(layout, figures)
            logging.info(f"Updated Data: {updated_layout}")
        except Exception as e:
            logging.error(f"Failed to merge figures into layout. Error: {e}")
            return {
                "recordId": record["recordId"],
                "data": {},
                "errors": [
                    {
                        "message": "Failed to merge figures into layout.",
                    }
                ],
                "warnings": None,
            }
        else:
            return {
                "recordId": record["recordId"],
                "data": updated_layout.model_dump(),
                "errors": None,
                "warnings": None,
            }
