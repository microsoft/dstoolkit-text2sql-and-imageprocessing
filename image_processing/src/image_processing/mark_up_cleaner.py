# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import json
import regex as re
from layout_holders import FigureHolder


class MarkUpCleaner:
    def get_sections(self, text) -> list:
        """
        Returns the section details from the content.

        Args:
            text: The input text

        Returns:
            list: The sections related to text
        """
        # Updated regex pattern to capture markdown headers like ### Header
        combined_pattern = r"(?<=\n|^)[#]+\s*(.*?)(?=\n)"
        doc_metadata = re.findall(combined_pattern, text, re.DOTALL)
        return self.clean_sections(doc_metadata)

    def get_figure_ids(self, text: str) -> list:
        """
        Get the FigureIds from the text.

        Args:
            text: The input text.

        Returns:
            list: The list of FigureIds."""
        # Regex pattern to extract FigureIds
        pattern = r"FigureId='([^']+)'"

        # Extract FigureIds using findall
        figure_ids = re.findall(pattern, text)

        return figure_ids

    def clean_sections(self, sections: list) -> list:
        """
        Cleans the sections by removing special characters and extra white spaces.
        """
        cleaned_sections = [re.sub(r"[=#]", "", match).strip() for match in sections]
        return cleaned_sections

    def remove_markdown_tags(self, text: str, tag_patterns: dict) -> str:
        """
        Remove specified Markdown tags from the text, keeping the contents of the tags.

        Args:
            text: The input text containing Markdown tags.
            tag_patterns: A dictionary where keys are tags and values are their specific patterns.

        Returns:
            str: The text with specified tags removed.
        """
        try:
            for tag, pattern in tag_patterns.items():
                try:
                    # Replace the tags using the specific pattern, keeping the content inside the tags
                    if tag == "header":
                        text = re.sub(
                            pattern, r"\2", text, flags=re.DOTALL | re.MULTILINE
                        )
                    else:
                        text = re.sub(pattern, r"\1", text, flags=re.DOTALL)
                except re.error as e:
                    logging.error(f"Regex error for tag '{tag}': {e}")
        except Exception as e:
            logging.error(f"An error occurred in remove_markdown_tags: {e}")
        return text

    def clean_text_and_extract_metadata(
        self, text: str, figures: list[FigureHolder]
    ) -> tuple[str, str]:
        """This function performs following cleanup activities on the text, remove all unicode characters
        remove line spacing,remove stop words, normalize characters

        Args:
            text (str): The input text to clean.
            figures (list): The list of figures.

        Returns:
            str: The clean text."""

        return_record = {}

        try:
            logging.info(f"Input text: {text}")
            if len(text) == 0:
                logging.error("Input text is empty")
                raise ValueError("Input text is empty")

            return_record["chunk_mark_up"] = text

            figure_ids = self.get_figure_ids(text)

            return_record["chunk_sections"] = self.get_sections(text)
            return_record["chunk_figures"] = [
                figure.model_dump(by_alias=True)
                for figure in figures
                if figure.figure_id in figure_ids
            ]

            logging.info(f"Sections: {return_record['chunk_sections']}")

            # Define specific patterns for each tag
            tag_patterns = {
                "figurecontent": r"<!-- FigureContent=(.*?)-->",
                "figure": r"<figure(?:\s+FigureId=\"[^\"]*\")?>(.*?)</figure>",
                "figures": r"\(figures/\d+\)(.*?)\(figures/\d+\)",
                "figcaption": r"<figcaption>(.*?)</figcaption>",
                "header": r"^\s*(#{1,6})\s*(.*?)\s*$",
            }
            cleaned_text = self.remove_markdown_tags(text, tag_patterns)

            logging.info(f"Removed markdown tags: {cleaned_text}")

            # Updated regex to keep Unicode letters, punctuation, whitespace, currency symbols, and percentage signs,
            # while also removing non-printable characters
            cleaned_text = re.sub(r"[^\p{L}\p{P}\s\p{Sc}%\x20-\x7E]", "", cleaned_text)

            logging.info(f"Cleaned text: {cleaned_text}")
            if len(cleaned_text) == 0:
                logging.error("Cleaned text is empty")
                raise ValueError("Cleaned text is empty")
            else:
                return_record["chunk_cleaned"] = cleaned_text
        except Exception as e:
            logging.error(f"An error occurred in clean_text_and_extract_metadata: {e}")
            return ""
        return return_record

    async def clean(self, record: dict) -> dict:
        """Cleanup the data using standard python libraries.

        Args:
            record (dict): The record to cleanup.

        Returns:
            dict: The clean record."""

        try:
            json_str = json.dumps(record, indent=4)

            logging.info(f"embedding cleaner Input: {json_str}")

            cleaned_record = {
                "recordId": record["recordId"],
                "data": {},
                "errors": None,
                "warnings": None,
            }

            figures = [FigureHolder(**figure) for figure in record["data"]["figures"]]

            cleaned_record["data"] = self.clean_text_and_extract_metadata(
                record["data"]["chunk"], figures
            )

        except Exception as e:
            logging.error("string cleanup Error: %s", e)
            return {
                "recordId": record["recordId"],
                "data": None,
                "errors": [
                    {
                        "message": "Failed to cleanup data. Check function app logs for more details of exact failure."
                    }
                ],
                "warnings": None,
            }
        json_str = json.dumps(cleaned_record, indent=4)

        logging.info(f"embedding cleaner output: {json_str}")
        return cleaned_record
