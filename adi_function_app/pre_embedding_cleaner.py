# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import json
import re


def get_section(cleaned_text: str) -> list:
    """
    Returns the section details from the content

    Args:
        cleaned_text: The input text

    Returns:
        list: The sections related to text

    """
    combined_pattern = r"(.*?)\n===|\n#+\s*(.*?)\n"
    doc_metadata = re.findall(combined_pattern, cleaned_text, re.DOTALL)
    doc_metadata = [match for group in doc_metadata for match in group if match]
    return clean_sections(doc_metadata)


def clean_sections(sections: list) -> list:
    """Cleans the sections by removing special characters and extra white spaces."""
    cleanedSections = [re.sub(r"[=#]", "", match).strip() for match in sections]

    return cleanedSections


def remove_markdown_tags(text: str, tag_patterns: dict) -> str:
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
                text = re.sub(pattern, r"\1", text, flags=re.DOTALL)
            except re.error as e:
                logging.error(f"Regex error for tag '{tag}': {e}")
    except Exception as e:
        logging.error(f"An error occurred in remove_markdown_tags: {e}")
    return text


def clean_text(src_text: str) -> str:
    """This function performs following cleanup activities on the text, remove all unicode characters
    remove line spacing,remove stop words, normalize characters

    Args:
        src_text (str): The text to cleanup.

    Returns:
        str: The clean text."""

    try:
        logging.info(f"Input text: {src_text}")
        if len(src_text) == 0:
            logging.error("Input text is empty")
            raise ValueError("Input text is empty")

        # Define specific patterns for each tag
        tag_patterns = {
            "figurecontent": r"<!-- FigureContent=(.*?)-->",
            "figure": r"<figure>(.*?)</figure>",
            "figures": r"\(figures/\d+\)(.*?)\(figures/\d+\)",
            "figcaption": r"<figcaption>(.*?)</figcaption>",
        }
        cleaned_text = remove_markdown_tags(src_text, tag_patterns)

        # Updated regex to keep Unicode letters, punctuation, whitespace, currency symbols, and percentage signs,
        # while also removing non-printable characters
        cleaned_text = re.sub(r"[^\p{L}\p{P}\s\p{Sc}%\x20-\x7E]", "", cleaned_text)

        logging.info(f"Cleaned text: {cleaned_text}")
        if len(cleaned_text) == 0:
            logging.error("Cleaned text is empty")
            raise ValueError("Cleaned text is empty")
    except Exception as e:
        logging.error(f"An error occurred in clean_text: {e}")
        return ""
    return cleaned_text


async def process_pre_embedding_cleaner(record: dict) -> dict:
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

        # scenarios when page by chunking is enabled
        if isinstance(record["data"]["chunk"], dict):
            cleaned_record["data"]["cleanedChunk"] = clean_text(
                record["data"]["chunk"]["content"]
            )
            cleaned_record["data"]["chunk"] = record["data"]["chunk"]["content"]
            cleaned_record["data"]["cleanedSections"] = clean_sections(
                record["data"]["chunk"]["sections"]
            )
        else:
            cleaned_record["data"]["cleanedChunk"] = clean_text(record["data"]["chunk"])
            cleaned_record["data"]["chunk"] = record["data"]["chunk"]
            cleaned_record["data"]["cleanedSections"] = get_section(
                record["data"]["chunk"]
            )

    except Exception as e:
        logging.error("string cleanup Error: %s", e)
        return {
            "recordId": record["recordId"],
            "data": {},
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
