# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# This code originates from: https://github.com/microsoft/dstoolkit-text2sql-and-imageprocessing
import logging
import json
import re
import tiktoken
import spacy
from sklearn.metrics.pairwise import cosine_similarity


class SemanticTextChunker:
    def __init__(
        self,
        num_surrounding_sentences=1,
        similarity_threshold=0.8,
        max_chunk_tokens=100,
    ):
        self.num_surrounding_sentences = num_surrounding_sentences
        self.similarity_threshold = similarity_threshold
        self.max_chunk_tokens = max_chunk_tokens
        try:
            self._nlp_model = spacy.load("en_core_web_md")
        except IOError as e:
            raise ValueError("Spacy model 'en_core_web_md' not found.") from e

    def sentence_contains_table(self, text: str) -> bool:
        """Detects if a sentence contains table tags.

        Args:
            text (str): The text to check.

        Returns:
            bool: If it contains a table."""
        return "<table>" in text or "</table>" in text

    def sentence_contains_figure(self, text: str) -> bool:
        """Detects if a sentence contains figure tags.

        Args:
            text (str): The text to check.

        Returns:
            bool: If it contains a figure."""
        return "<figure>" in text or "</figure>" in text

    def num_tokens_from_string(self, string: str) -> int:
        """Gets the number of tokens in a string using a specific encoding.

        Args:
            string: The input string.

        Returns:
            int: The number of tokens in the string."""
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(string))

    def get_sections(self, cleaned_text: str) -> list:
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
        return self.clean_sections(doc_metadata)

    def clean_sections(self, sections: list) -> list:
        """Cleans the sections by removing special characters and extra white spaces."""
        cleaned_sections = [re.sub(r"[=#]", "", match).strip() for match in sections]

        return cleaned_sections

    async def chunk(self, text: str) -> list[dict]:
        """Attempts to chunk the text and then assigns the sections from the relevant chunk, to a separate field.

        Args:
            text (str): The set of text to chunk

        Returns:
            list(dict): The list of matching chunks and sections"""
        final_chunks = self.chunk_into_sentences(text)

        # now extract section data
        chunk_and_section_output = []
        for chunk in final_chunks:
            sections = self.get_sections(chunk)

            chunk_and_section_output.append({"content": chunk, "sections": sections})

        return chunk_and_section_output

    def chunk_into_sentences(self, text: str) -> list[str]:
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
        forward_pass_chunks, is_table_or_figure_map = self.merge_chunks(
            grouped_sentences, is_table_or_figure_map
        )

        backwards_pass_chunks, _ = self.merge_chunks(
            forward_pass_chunks, is_table_or_figure_map, forwards_direction=False
        )
        return backwards_pass_chunks

    def split_into_sentences(self, text: str) -> list[str]:
        """Splits a set of text into a list of sentences uses the Spacy NLP model.

        Args:
            text (str): The set of text to chunk

        Returns:
            list(str): The extracted sentences
        """
        doc = self._nlp_model(text)
        sentences = [sent.text for sent in doc.sents]
        return sentences

    def group_figures_and_tables_into_sentences(self, sentences):
        grouped_sentences = []
        holding_sentences = []

        is_table_or_figure_map = []

        is_grouped_sentence = False
        for current_sentence in sentences:
            if is_grouped_sentence is False:
                if self.sentence_contains_figure(
                    current_sentence
                ) or self.sentence_contains_table(current_sentence):
                    is_grouped_sentence = True
                    holding_sentences.append(current_sentence)
                else:
                    grouped_sentences.append(current_sentence)
                    is_table_or_figure_map = False
            else:
                # check for ending case
                if self.sentence_contains_figure(
                    current_sentence
                ) or self.sentence_contains_table(current_sentence):
                    holding_sentences.append(current_sentence)

                    full_sentence = " ".join(holding_sentences)
                    grouped_sentences.append(full_sentence)
                    holding_sentences = []

                    is_grouped_sentence = False
                    is_table_or_figure_map = True
                else:
                    holding_sentences.append(current_sentence)

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
        if current_sentence_index + self.num_surrounding_sentences > total_sentences:
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

    def merge_similar_chunks(self, current_sentence, current_chunk):
        new_chunk = None
        # Current chunk will be updated in place
        # Only compare when we have 2 or more chunks
        if len(current_chunk) >= 2:
            cosine_sim = self.sentence_similarity(
                " ".join(current_chunk[-2:]), current_sentence
            )
            if (
                cosine_sim < self.similarity_threshold
                or self.num_tokens_from_string(" ".join(current_chunk))
                > self.max_chunk_tokens
            ):
                if len(current_chunk) > 2:
                    new_chunk = " ".join(current_chunk[:-1])
                    current_chunk = [current_chunk[-1]]
                else:
                    new_chunk = current_chunk[0]
                    current_chunk = [current_chunk[1]]

        return new_chunk

    def merge_chunks(self, sentences, is_table_or_figure_map, forwards_direction=True):
        chunks = []
        current_chunk = []

        total_sentences = len(sentences)
        index = 0

        new_is_table_or_figure_map = []
        while index < total_sentences:
            if forwards_direction is False:
                current_sentence_index = total_sentences - index
            else:
                current_sentence_index = index

            current_sentence = sentences[current_sentence_index]

            # Detect if table or figure
            if is_table_or_figure_map[current_sentence_index]:
                if forwards_direction:
                    current_chunk.append(current_chunk)
                else:
                    # On the backwards pass we don't want to add to the table chunk
                    chunks.append(" ".join(current_chunk))
                    chunks.append(current_chunk)
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
                    # Finish off
                    current_chunk.append(current_sentence)
                    chunks.append(" ".join(current_chunk))
                    new_is_table_or_figure_map.append(True)
                    current_chunk = []
                    continue
                elif is_table_or_figure_ahead:
                    # Add to the ahead chunk
                    chunks.append(" ".join(current_chunk))
                    new_is_table_or_figure_map.append(True)
                    current_chunk = sentences[
                        current_sentence_index:min_of_distance_to_next_figure_or_num_surrounding_sentences
                    ]

                    index += min_of_distance_to_next_figure_or_num_surrounding_sentences
                    continue

            # now group semanticly
            num_tokens = self.num_tokens_from_string(current_sentence)

            if num_tokens >= self.max_chunk_tokens:
                chunks.append(current_sentence)
                new_is_table_or_figure_map.append(False)
                continue
            else:
                current_chunk.append(current_sentence)

            new_chunk = self.merge_similar_chunks(current_sentence, current_chunk)

            if new_chunk is not None:
                chunks.append(new_chunk)
                new_is_table_or_figure_map.append(False)

            index += 1

        if len(current_chunk) > 0:
            chunks.append(" ".join(current_chunk))
            new_is_table_or_figure_map.append(False)

        return chunks, new_is_table_or_figure_map

    def sentence_similarity(self, text1, text2):
        vec1 = self._nlp_model(text1).vector
        vec2 = self._nlp_model(text2).vector
        return cosine_similarity([vec1], [vec2])[0, 0]


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
        cleaned_record["data"] = await text_chunker.chunk(record["data"]["content"])

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
