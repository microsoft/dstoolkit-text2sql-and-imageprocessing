# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import re
from layout_holders import FigureHolder, LayoutHolder
from typing import List


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
            int: The change in length of the Markdown content after updating the figure description.
        """
        # Calculate the end index of the content to be replaced
        end_index = figure_holder.offset + figure_holder.length

        # Ensure the offset is valid
        if figure_holder.offset < 0 or figure_holder.offset > len(
            layout_holder.content
        ):
            logging.error("Figure offset is out of bounds.")
            raise ValueError("Figure offset is out of bounds.")

        # Ensure the end index does not exceed the length of the Markdown content
        if end_index > len(layout_holder.content):
            logging.info(
                "End index exceeds the length of the content. Adjusting to the length of the content."
            )
            end_index = len(layout_holder.content)

        logging.info(f"Figure Markdown Content: {figure_holder.markdown}")

        # Replace the old string with the new string
        layout_holder.content = (
            layout_holder.content[: figure_holder.offset]
            + figure_holder.markdown
            + layout_holder.content[end_index:]
        )

        inserted_length = len(figure_holder.markdown) - figure_holder.length
        logging.info(f"Inserted Length: {inserted_length}")

        return layout_holder, inserted_length

    async def merge_figures_into_layout(
        self, layout_holder: LayoutHolder, figures: List[FigureHolder]
    ) -> LayoutHolder:
        """
        Merges the figures into the layout.

        Args:
            layout_holder (LayoutHolder): The layout text.
            figures (List[FigureHolder]): The list of figures.

        Returns:
            LayoutHolder: The updated layout text with the figures.
        """
        # Initialize the offset
        running_offset = 0

        # Iterate over the figures
        for figure in figures:
            logging.info(f"Inserting Figure: {figure.figure_id}")
            logging.info(f"Figure Description: {figure.description}")
            # Update the figure description in the layout
            figure.offset += running_offset
            layout_holder, inserted_length = self.insert_figure_description(
                layout_holder, figure
            )

            # Update the offset
            running_offset += inserted_length

        logging.info("Merged figures into layout.")
        logging.info("Updated Layout with Figures: %s", layout_holder.content)
        # Precompile regex patterns
        irrelevant_figure_pattern = re.compile(
            r"<figure[^>]*>\s*(Irrelevant Image|\'Irrelevant Image\')\s*</figure>",
            re.DOTALL,
        )
        empty_or_whitespace_figure_pattern = re.compile(
            r"<figure[^>]*>\s*</figure>", re.DOTALL
        )
        html_comments_pattern = re.compile(r"<!--.*?-->", re.DOTALL)

        # Remove irrelevant figures
        layout_holder.content = irrelevant_figure_pattern.sub("", layout_holder.content)
        logging.info("Removed irrelevant figures from layout.")
        logging.info(
            "Updated Layout without Irrelevant Figures: %s", layout_holder.content
        )

        # Remove empty or whitespace figures
        layout_holder.content = empty_or_whitespace_figure_pattern.sub(
            "", layout_holder.content
        )
        logging.info("Removed empty or whitespace figures from layout.")
        logging.info(
            "Updated Layout without Empty or Whitespace Figures: %s",
            layout_holder.content,
        )

        # Remove HTML comments
        layout_holder.content = html_comments_pattern.sub("", layout_holder.content)
        logging.info("Removed HTML comments from layout.")
        logging.info("Updated Layout without HTML Comments: %s", layout_holder.content)

        return layout_holder

    async def merge(self, record: dict) -> dict:
        """
        Analyse the image and generate a description for it.

        Parameters:
        - record (dict): The record containing the image and its caption.

        Returns:
        - record (dict): The record containing the image, its caption, and the generated description.
        """
        layout_holder = LayoutHolder(**record["data"]["layout"])

        figures = [FigureHolder(**figure) for figure in record["data"]["figures"]]

        try:
            logging.info(f"Input Data: {layout_holder}")
            updated_layout = await self.merge_figures_into_layout(
                layout_holder, figures
            )
            logging.info(f"Updated Layout Data: {updated_layout}")
        except Exception as e:
            logging.error(f"Failed to merge figures into layout. Error: {e}")
            return {
                "recordId": record["recordId"],
                "data": None,
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
