# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import json
import re
import tiktoken
import spacy
import numpy as np

logging.basicConfig(level=logging.INFO)


class SemanticTextChunker:
    def __init__(
        self,
        num_surrounding_sentences: int = 1,
        similarity_threshold: float = 0.8,
        max_chunk_tokens: int = 200,
        min_chunk_tokens: int = 50,
    ):
        self.num_surrounding_sentences = num_surrounding_sentences
        self.similarity_threshold = similarity_threshold
        self.max_chunk_tokens = max_chunk_tokens
        self.min_chunk_tokens = min_chunk_tokens
        try:
            self._nlp_model = spacy.load("en_core_web_md")
        except IOError as e:
            raise ValueError("Spacy model 'en_core_web_md' not found.") from e

    def sentence_contains_figure_or_table_ending(self, text: str):
        return "</figure>" in text or "</table>" in text

    def sentence_contains_figure_or_table(self, text: str):
        return (
            ("<figure" in text or "</figure>" in text)
            or ("<table>" in text or "</table>" in text)
            or ("<th" in text or "th>" in text)
            or ("<td" in text or "td>" in text)
        )

    def sentence_is_complete_figure_or_table(self, text: str):
        return ("<figure" in text and "</figure>" in text) or (
            "<table>" in text and "</table>" in text
        )

    def num_tokens_from_string(self, string: str) -> int:
        """Gets the number of tokens in a string using a specific encoding.

        Args:
            string: The input string.

        Returns:
            int: The number of tokens in the string."""

        encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(string))

    async def chunk(self, text: str) -> list[dict]:
        """Attempts to chunk the text by:
            Splitting into sentences
            Grouping sentences that contain figures and tables
            Merging semanticly similar chunks

        Args:
            text (str): The set of text to chunk

        Returns:
            list(str): The list of chunks"""

        sentences = self.split_into_sentences(text)

        (
            grouped_sentences,
            is_table_or_figure_map,
        ) = self.group_figures_and_tables_into_sentences(sentences)

        forward_pass_chunks, new_is_table_or_figure_map = self.merge_chunks(
            grouped_sentences, is_table_or_figure_map
        )

        logging.info(
            f"""Number of Forward pass chunks: {
                len(forward_pass_chunks)}"""
        )
        logging.info(f"Forward pass chunks: {forward_pass_chunks}")

        backwards_pass_chunks, _ = self.merge_chunks(
            forward_pass_chunks, new_is_table_or_figure_map, forwards_direction=False
        )

        reversed_backwards_pass_chunks = list(reversed(backwards_pass_chunks))

        logging.info(
            f"""Number of Backaward pass chunks: {
                len(reversed_backwards_pass_chunks)}"""
        )
        logging.info(f"Backward pass chunks: {reversed_backwards_pass_chunks}")

        cleaned_final_chunks = []
        for chunk in reversed_backwards_pass_chunks:
            stripped_chunk = chunk.strip()
            if len(stripped_chunk) > 0:
                cleaned_final_chunks.append(stripped_chunk)

        logging.info(f"Number of final chunks: {len(cleaned_final_chunks)}")
        logging.info(f"Chunks: {cleaned_final_chunks}")

        return cleaned_final_chunks

    def filter_empty_figures(self, text):
        # Regular expression to match <figure>...</figure> with only newlines or spaces in between
        pattern = r"<figure>\s*</figure>"

        # Replace any matches of the pattern with an empty string
        filtered_text = re.sub(pattern, "", text)

        return filtered_text

    def clean_new_lines(self, text):
        # Remove single newlines surrounded by < and >
        cleaned_text = re.sub(r"(?<=>)(\n)(?=<)", "", text)

        # Replace all other single newlines with space
        cleaned_text = re.sub(r"(?<!\n)\n(?!\n)", " ", cleaned_text)

        # Replace multiple consecutive newlines with a single space followed by \n\n
        cleaned_text = re.sub(r"\n{2,}", " \n\n", cleaned_text)
        return cleaned_text

    def split_into_sentences(self, text: str) -> list[str]:
        """Splits a set of text into a list of sentences uses the Spacy NLP model.

        Args:
            text (str): The set of text to chunk

        Returns:
            list(str): The extracted sentences
        """

        cleaned_text = self.clean_new_lines(text)

        # Filter out empty <figure>...</figure> tags
        cleaned_text = self.filter_empty_figures(cleaned_text)

        doc = self._nlp_model(cleaned_text)

        tag_split_sentences = []
        # Pattern to match the closing and opening tag junctions with whitespace in between
        split_pattern = r"(</table>\s*<table\b[^>]*>|</figure>\s*<figure\b[^>]*>)"
        for sent in doc.sents:
            split_result = re.split(split_pattern, sent.text)
            for part in split_result:
                # Match the junction and split it into two parts
                if re.match(split_pattern, part):
                    # Split at the first whitespace
                    tag_split = part.split(" ", 1)
                    # Add the closing tag (e.g., </table>)
                    tag_split_sentences.append(tag_split[0])
                    if len(tag_split) > 1:
                        # Add the rest of the string with leading space
                        tag_split_sentences.append(" " + tag_split[1])
                else:
                    tag_split_sentences.append(part)

        # Now apply a split pattern against markdown headings
        heading_split_sentences = []

        # Iterate through each sentence in tag_split_sentences
        for sent in tag_split_sentences:
            # Use re.split to split on \n\n and headings, but keep \n\n in the result
            split_result = re.split(r"(\n\n|#+ .*)", sent)

            # Extend the result with the correctly split parts, retaining \n\n before the heading
            for part in split_result:
                if part.strip():  # Only add non-empty parts
                    if (
                        self.is_markdown_heading(part)
                        and part.endswith("\n\n") is False
                    ):
                        part = part + "\n\n"
                    heading_split_sentences.append(part)

        return heading_split_sentences

    def group_figures_and_tables_into_sentences(self, sentences: list[str]):
        grouped_sentences = []
        holding_sentences = []

        is_table_or_figure_map = []

        is_grouped_sentence = False
        for current_sentence in sentences:
            if is_grouped_sentence is False:
                if self.sentence_is_complete_figure_or_table(current_sentence):
                    grouped_sentences.append(current_sentence)
                    is_table_or_figure_map.append(True)
                elif self.sentence_contains_figure_or_table(current_sentence):
                    is_grouped_sentence = True
                    holding_sentences.append(current_sentence)
                else:
                    grouped_sentences.append(current_sentence)
                    is_table_or_figure_map.append(False)
            else:
                # check for ending case
                if self.sentence_contains_figure_or_table_ending(current_sentence):
                    holding_sentences.append(current_sentence)

                    full_sentence = " ".join(holding_sentences)
                    grouped_sentences.append(full_sentence)
                    holding_sentences = []

                    is_grouped_sentence = False
                    is_table_or_figure_map.append(True)
                else:
                    holding_sentences.append(current_sentence)

        assert len(holding_sentences) == 0, "Holding sentences should be empty"

        return grouped_sentences, is_table_or_figure_map

    def look_ahead_and_behind_sentences(
        self, total_sentences, is_table_or_figure_map, current_sentence_index
    ):
        is_table_or_figure_ahead = False
        is_table_or_figure_behind = False

        distance_to_next_figure = self.num_surrounding_sentences

        if current_sentence_index < self.num_surrounding_sentences:
            is_table_or_figure_behind = is_table_or_figure_map[0]
        else:
            is_table_or_figure_behind = is_table_or_figure_map[
                current_sentence_index - self.num_surrounding_sentences
            ]

        surround_sentences_gap_to_test = self.num_surrounding_sentences
        if current_sentence_index + self.num_surrounding_sentences >= total_sentences:
            is_table_or_figure_ahead = is_table_or_figure_map[-1]
            surround_sentences_gap_to_test = total_sentences - current_sentence_index
        else:
            is_table_or_figure_ahead = is_table_or_figure_map[
                current_sentence_index + self.num_surrounding_sentences
            ]

        for (
            next_sentence_is_table_or_figure_index,
            next_sentence_is_table_or_figure,
        ) in enumerate(
            is_table_or_figure_map[
                current_sentence_index : current_sentence_index
                + surround_sentences_gap_to_test
            ]
        ):
            if next_sentence_is_table_or_figure:
                distance_to_next_figure = next_sentence_is_table_or_figure_index

        return (
            is_table_or_figure_ahead,
            is_table_or_figure_behind,
            min(surround_sentences_gap_to_test, distance_to_next_figure),
        )

    def merge_similar_chunks(self, current_sentence, current_chunk, forwards_direction):
        new_chunk = None

        def retrieve_current_chunk_up_to_n(n):
            if forwards_direction:
                return " ".join(current_chunk[:-n])
            else:
                return " ".join(reversed(current_chunk[:-n]))

        def retrieve_current_chunks_from_n(n):
            if forwards_direction:
                return " ".join(current_chunk[n:])
            else:
                return " ".join(reversed(current_chunk[:-n]))

        def retrive_current_chunk_at_n(n):
            if forwards_direction:
                return current_chunk[n]
            else:
                return current_chunk[n]

        current_chunk_tokens = self.num_tokens_from_string(" ".join(current_chunk))

        if len(current_chunk) >= 2 and current_chunk_tokens >= self.min_chunk_tokens:
            logging.debug("Comparing chunks")
            cosine_sim = self.sentence_similarity(
                retrieve_current_chunks_from_n(-2), current_sentence
            )
            if (
                cosine_sim < self.similarity_threshold
                or current_chunk_tokens >= self.max_chunk_tokens
            ):
                if len(current_chunk) > 2:
                    new_chunk = retrieve_current_chunk_up_to_n(1)
                    current_chunk = [retrive_current_chunk_at_n(-1)]
                else:
                    new_chunk = retrive_current_chunk_at_n(0)
                    current_chunk = [retrive_current_chunk_at_n(1)]
        else:
            logging.debug("Chunk too small to compare")

        return new_chunk, current_chunk

    def is_markdown_heading(self, text):
        return text.strip().startswith("#")

    def merge_chunks(self, sentences, is_table_or_figure_map, forwards_direction=True):
        chunks = []
        current_chunk = []

        total_sentences = len(sentences)
        index = 0

        def retrieve_current_chunk():
            if forwards_direction:
                return " ".join(current_chunk)
            else:
                return " ".join(reversed(current_chunk))

        new_is_table_or_figure_map = []
        while index < total_sentences:
            if forwards_direction is False:
                current_sentence_index = total_sentences - index - 1
            else:
                current_sentence_index = index

            current_sentence = sentences[current_sentence_index]

            if len(current_sentence.strip()) == 0:
                index += 1
                continue

            # Detect if table or figure
            if is_table_or_figure_map[current_sentence_index]:
                if forwards_direction:
                    if len(current_chunk) > 0:
                        current_chunk.append(current_sentence)
                        chunks.append(retrieve_current_chunk())
                        new_is_table_or_figure_map.append(True)
                        current_chunk = []
                    else:
                        current_chunk.append(current_sentence)
                else:
                    # On the backwards pass we don't want to add to the table chunk
                    chunks.append(retrieve_current_chunk())
                    new_is_table_or_figure_map.append(True)
                    current_chunk = [current_sentence]

                index += 1
                continue
            elif forwards_direction:
                # Look ahead to see if figure of table is coming up
                # We only do this on the forward pass
                (
                    is_table_or_figure_ahead,
                    is_table_or_figure_behind,
                    min_of_distance_to_next_figure_or_num_surrounding_sentences,
                ) = self.look_ahead_and_behind_sentences(
                    total_sentences, is_table_or_figure_map, current_sentence_index
                )

                if is_table_or_figure_behind:
                    # Check if Makrdown heading
                    if self.is_markdown_heading(current_sentence):
                        # Start new chunk
                        chunks.append(retrieve_current_chunk())
                        new_is_table_or_figure_map.append(False)
                        current_chunk = [current_sentence]
                    else:
                        # Finish off
                        current_chunk.append(current_sentence)
                        chunks.append(retrieve_current_chunk())
                        new_is_table_or_figure_map.append(False)
                        current_chunk = []

                    index += 1
                    continue
                elif is_table_or_figure_ahead:
                    # Add to the ahead chunk
                    chunks.append(retrieve_current_chunk())
                    new_is_table_or_figure_map.append(False)
                    if forwards_direction:
                        current_chunk = sentences[
                            current_sentence_index : current_sentence_index
                            + min_of_distance_to_next_figure_or_num_surrounding_sentences
                        ]
                    else:
                        current_chunk = sentences[
                            current_sentence_index : current_sentence_index
                            - min_of_distance_to_next_figure_or_num_surrounding_sentences : -1
                        ]
                    index += min_of_distance_to_next_figure_or_num_surrounding_sentences
                    continue

            # now group semanticly
            num_tokens = self.num_tokens_from_string(current_sentence)

            if num_tokens >= self.max_chunk_tokens:
                chunks.append(current_sentence)
                new_is_table_or_figure_map.append(False)
            else:
                current_chunk.append(current_sentence)

                new_chunk, current_chunk = self.merge_similar_chunks(
                    current_sentence,
                    current_chunk,
                    forwards_direction=forwards_direction,
                )

                if new_chunk is not None:
                    chunks.append(new_chunk)
                    new_is_table_or_figure_map.append(False)

            index += 1

        if len(current_chunk) > 0:
            final_chunk = retrieve_current_chunk()
            chunks.append(final_chunk)

            new_is_table_or_figure_map.append(
                self.sentence_contains_figure_or_table(final_chunk)
            )

        return chunks, new_is_table_or_figure_map

    def sentence_similarity(self, text_1, text_2):
        vec1 = self._nlp_model(text_1).vector
        vec2 = self._nlp_model(text_2).vector

        dot_product = np.dot(vec1, vec2)
        magnitude = np.linalg.norm(vec1) * np.linalg.norm(vec2)
        similarity = dot_product / magnitude if magnitude != 0 else 0.0

        logging.debug(
            f"""Similarity between '{text_1}' and '{
                text_2}': {similarity}"""
        )
        return similarity


async def process_semantic_text_chunker(record: dict, text_chunker) -> dict:
    """Chunk the data.

    Args:
        record (dict): The record to cleanup.

    Returns:
        dict: The clean record."""

    try:
        json_str = json.dumps(record, indent=4)

        logging.info(f"Chunking Input: {json_str}")

        cleaned_record = {
            "recordId": record["recordId"],
            "data": {},
            "errors": None,
            "warnings": None,
        }

        # scenarios when page by chunking is enabled
        cleaned_record["data"]["chunks"] = await text_chunker.chunk(
            record["data"]["content"]
        )

    except Exception as e:
        logging.error("Chunking Error: %s", e)
        return {
            "recordId": record["recordId"],
            "data": {},
            "errors": [
                {
                    "message": "Failed to chunk data. Check function app logs for more details of exact failure."
                }
            ],
            "warnings": None,
        }
    json_str = json.dumps(cleaned_record, indent=4)

    logging.info(f"Chunking output: {json_str}")

    return cleaned_record
