# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import json
import re
import tiktoken
import spacy
import numpy as np
from model2vec import StaticModel
from layout_holders import PageNumberTrackingHolder, ChunkHolder


class SemanticTextChunker:
    def __init__(
        self,
        similarity_threshold: float = 0.8,
        max_chunk_tokens: int = 500,
        min_chunk_tokens: int = 200,
    ):
        self.similarity_threshold = similarity_threshold
        self.max_chunk_tokens = max_chunk_tokens
        self.min_chunk_tokens = min_chunk_tokens

        model_name = "minishlab/M2V_base_output"
        self.distilled_model = StaticModel.from_pretrained(model_name)

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

    def clean_chunks_and_map(self, chunks, is_table_or_figure_map):
        cleaned_chunks = []
        cleaned_is_table_or_figure_map = []

        for current_chunk, is_table_or_figure in zip(chunks, is_table_or_figure_map):
            cleaned_chunk = current_chunk.strip()
            if len(cleaned_chunk) > 0:
                # Add a newline if the chunk ends with a newline (it was a title)
                if self.is_markdown_heading(current_chunk):
                    cleaned_chunk = "\n\n" + cleaned_chunk + "\n\n"

                cleaned_chunks.append(cleaned_chunk)
                cleaned_is_table_or_figure_map.append(is_table_or_figure)

        return cleaned_chunks, cleaned_is_table_or_figure_map

    async def chunk(self, text: str) -> list[ChunkHolder]:
        """Attempts to chunk the text by:
            Splitting into sentences
            Grouping sentences that contain figures and tables
            Merging semanticly similar chunks

        Args:
            text (str): The set of text to chunk

        Returns:
            list(str): The list of chunks"""

        logging.debug(f"Chunking text: {text}")

        sentences = self.split_into_sentences(text)

        logging.info(f"Number of sentences: {len(sentences)}")

        (
            grouped_sentences,
            is_table_or_figure_map,
        ) = self.group_figures_and_tables_into_sentences(sentences)

        forward_pass_chunks, new_is_table_or_figure_map = self.merge_chunks(
            grouped_sentences, is_table_or_figure_map
        )

        forward_pass_chunks, new_is_table_or_figure_map = self.clean_chunks_and_map(
            forward_pass_chunks, new_is_table_or_figure_map
        )

        logging.info(
            f"""Number of Forward pass chunks: {
                len(forward_pass_chunks)}"""
        )
        logging.debug(f"Forward pass chunks: {forward_pass_chunks}")

        backwards_pass_chunks, _ = self.merge_chunks(
            forward_pass_chunks, new_is_table_or_figure_map, forwards_direction=False
        )

        reversed_backwards_pass_chunks = list(reversed(backwards_pass_chunks))

        logging.info(
            f"""Number of Backaward pass chunks: {
                len(reversed_backwards_pass_chunks)}"""
        )
        logging.debug(f"Backward pass chunks: {reversed_backwards_pass_chunks}")

        cleaned_final_chunks = []
        for chunk in reversed_backwards_pass_chunks:
            stripped_chunk = chunk.strip()
            if len(stripped_chunk) > 0:
                cleaned_final_chunks.append(ChunkHolder(mark_up=stripped_chunk))

        logging.info(f"Number of final chunks: {len(cleaned_final_chunks)}")
        logging.debug(f"Chunks: {cleaned_final_chunks}")

        if len(cleaned_final_chunks) == 0:
            raise ValueError("No chunks were generated")

        return cleaned_final_chunks

    def filter_empty_figures(self, text):
        # Regular expression to match <figure>...</figure> with only newlines or spaces in between
        pattern = r"<figure>\s*</figure>"

        # Replace any matches of the pattern with an empty string
        filtered_text = re.sub(pattern, "", text)

        return filtered_text

    def clean_new_lines(self, text):
        # Remove single newlines surrounded by < and >
        cleaned_text = re.sub(r"(?<=>)(\n)(?=<)", "", text.strip())

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

        logging.debug(f"Cleaned text: {cleaned_text}")

        self._nlp_model.max_length = len(cleaned_text) + 100
        doc = self._nlp_model(
            cleaned_text, disable=["ner", "tagger", "lemmatizer", "textcat"]
        )

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
                        part = "\n\n" + part + "\n\n"

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

        if len(holding_sentences) > 0:
            full_sentence = " ".join(holding_sentences)
            grouped_sentences.append(full_sentence)
            holding_sentences = []

            is_table_or_figure_map.append(True)

        return grouped_sentences, is_table_or_figure_map

    def remove_figures(self, text):
        figure_tag_pattern = (
            r"<figure(?:\s+FigureId=(\"[^\"]*\"|'[^']*'))?>(.*?)</figure>"
        )
        return re.sub(figure_tag_pattern, "", text).strip()

    def merge_similar_chunks(self, current_sentence, current_chunk, forwards_direction):
        new_chunk = None

        def retrieve_current_chunk_up_to_minus_n(n):
            if forwards_direction:
                return " ".join(current_chunk[:-n])
            else:
                return " ".join(reversed(current_chunk[:-n]))

        def retrive_current_chunk_at_n(n):
            if forwards_direction:
                return current_chunk[n]
            else:
                return current_chunk[n]

        def retrieve_current_chunks_from_n(n):
            if forwards_direction:
                return " ".join(current_chunk[n:])
            else:
                return " ".join(reversed(current_chunk[n:]))

        def get_current_chunk_tokens(chunk_segments):
            if isinstance(chunk_segments, str):
                return self.num_tokens_from_string(chunk_segments)

            return self.num_tokens_from_string(" ".join(chunk_segments))

        if len(current_chunk) == 1:
            logging.debug("Chunk too small to compare")
            return new_chunk, current_chunk

        if len(current_chunk) > 2:
            would_be_end_of_old_chunk = retrieve_current_chunk_up_to_minus_n(1)
            would_be_start_of_new_chunk = [retrive_current_chunk_at_n(-1)]
        else:
            would_be_end_of_old_chunk = retrive_current_chunk_at_n(0)
            would_be_start_of_new_chunk = [retrive_current_chunk_at_n(1)]

        current_chunk_tokens = get_current_chunk_tokens(current_chunk)
        logging.debug(f"Current chunk tokens: {current_chunk_tokens}")
        would_be_end_of_old_chunk_tokens = get_current_chunk_tokens(
            would_be_end_of_old_chunk
        )
        logging.debug(f"Would be new chunk tokens: {would_be_end_of_old_chunk_tokens}")

        would_be_end_of_old_chunk_without_figures = self.remove_figures(
            would_be_end_of_old_chunk
        )

        would_be_end_of_old_chunk_without_figures_tokens = self.num_tokens_from_string(
            would_be_end_of_old_chunk_without_figures
        )

        would_be_start_of_new_chunk_without_figures = self.remove_figures(
            " ".join(would_be_start_of_new_chunk)
        )

        if len(would_be_start_of_new_chunk_without_figures) == 0:
            logging.debug("Chunk would only contain figures. Not comparing")
            return new_chunk, current_chunk

        if (
            would_be_end_of_old_chunk_tokens < self.min_chunk_tokens
            or would_be_end_of_old_chunk_without_figures_tokens
            < (self.min_chunk_tokens / 2)
        ):
            logging.debug("Chunk too small. Not comparing")
            return new_chunk, current_chunk

        if would_be_end_of_old_chunk_without_figures_tokens > self.max_chunk_tokens:
            logging.debug("Chunk too large. Not comparing")
            return would_be_end_of_old_chunk, would_be_start_of_new_chunk

        similarity_set = retrieve_current_chunks_from_n(-2)

        # Calculate the tokens if we were to split
        logging.debug("Comparing chunks")
        if (
            current_chunk_tokens > (self.max_chunk_tokens * 1.5)
            or self.sentence_similarity(similarity_set, current_sentence)
            < self.similarity_threshold
        ):
            return would_be_end_of_old_chunk, would_be_start_of_new_chunk
        else:
            logging.debug("Above similarity threshold")
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

            if forwards_direction and self.is_markdown_heading(current_sentence):
                heading_level = current_sentence.count("#")

                if heading_level in [1, 2]:
                    # Start new chunk
                    if len(current_chunk) > 0:
                        current_chunk = retrieve_current_chunk()
                        chunks.append(current_chunk)
                        new_is_table_or_figure_map.append(
                            self.sentence_contains_figure_or_table(current_chunk)
                        )
                        current_chunk = [current_sentence]

                        index += 1
                        continue

            # Detect if table or figure
            if forwards_direction and is_table_or_figure_map[current_sentence_index]:
                if len(current_chunk) > 0:
                    current_chunk.append(current_sentence)
                    chunks.append(retrieve_current_chunk())
                    new_is_table_or_figure_map.append(True)
                    current_chunk = []

                    index += 1
                    continue

            # now group semanticly
            current_chunk.append(current_sentence)

            new_chunk, current_chunk = self.merge_similar_chunks(
                current_sentence,
                current_chunk,
                forwards_direction=forwards_direction,
            )

            if new_chunk is not None:
                chunks.append(new_chunk)
                new_is_table_or_figure_map.append(
                    self.sentence_contains_figure_or_table(new_chunk)
                )

            index += 1

        if len(current_chunk) > 0:
            final_chunk = retrieve_current_chunk()

            # Get tokens of this chunk
            if (
                self.num_tokens_from_string(final_chunk) < self.min_chunk_tokens
                and len(chunks) > 0
            ):
                # Add the last chunk to the new chunks
                if forwards_direction:
                    final_chunk = chunks[-1] + " " + final_chunk
                else:
                    final_chunk = final_chunk + " " + chunks[-1]

                chunks[-1] = final_chunk
                new_is_table_or_figure_map[-1] = self.sentence_contains_figure_or_table(
                    final_chunk
                )
            else:
                chunks.append(final_chunk)
                new_is_table_or_figure_map.append(
                    self.sentence_contains_figure_or_table(final_chunk)
                )

        return chunks, new_is_table_or_figure_map

    def sentence_similarity(self, text_1, text_2):
        vec1 = self.distilled_model.encode(text_1)
        vec2 = self.distilled_model.encode(text_2)

        dot_product = np.dot(vec1, vec2)
        magnitude = np.linalg.norm(vec1) * np.linalg.norm(vec2)
        similarity = dot_product / magnitude if magnitude != 0 else 0.0

        logging.debug(
            f"""Similarity between '{text_1}' and '{
                text_2}': {similarity}"""
        )
        return similarity

    def assign_page_number_to_chunks(
        self,
        chunks: list[ChunkHolder],
        page_number_tracking_holders: list[PageNumberTrackingHolder],
    ) -> list[ChunkHolder]:
        """Assigns page numbers to the chunks based on the starting sentences of each page.

        Args:
            chunks (list[ChunkHolder]): The list of chunks.
            page_number_tracking_holders (list[PageNumberTrackingHolder]): The list of starting sentences of each page.

        Returns:
            list[ChunkHolder]: The list of chunks with page numbers assigned."""
        page_number = 1
        for chunk in chunks:
            # Remove any leading whitespace/newlines.
            cleaned_content = chunk.mark_up.lstrip()
            # Strip the html comment but keep the content
            html_comments_pattern = re.compile(r"<!--.*?-->", re.DOTALL)
            cleaned_content = html_comments_pattern.sub("", cleaned_content)

            # Use the nlp model to get the first sentence
            sentences = list(
                self._nlp_model(
                    cleaned_content, disable=["ner", "tagger", "lemmatizer", "textcat"]
                ).sents
            )

            if len(sentences) == 0:
                first_line = None
            else:
                first_sentence = sentences[0].text.strip()

                if "#" in first_sentence:
                    logging.info("Splitting on hash")
                    # Delibretely split on the next hash to get the first line of the markdown content
                    first_line = (
                        first_sentence.split(" #", 1)[0]
                        .strip()
                        .split("\n", 1)[0]
                        .strip()
                    )
                elif "<table>" in first_sentence:
                    logging.info("Joining onto second sentence to form first row")
                    if len(sentences) > 1:
                        first_line = (
                            first_sentence.lstrip() + "\n" + sentences[1].text.strip()
                        )
                    else:
                        first_line = first_sentence
                elif "\n" in first_sentence:
                    logging.info("Splitting on newline")
                    first_line = first_sentence.split("\n", 1)[0].strip()
                elif "." in first_sentence:
                    logging.info("Splitting on period")
                    first_line = first_sentence.split(".", 1)[0].strip()
                else:
                    logging.info("No split found")
                    first_line = first_sentence.strip()

            if first_line is not None:
                logging.info(f"Looking for First line: {first_line}")
                for page_number_tracking_holder in page_number_tracking_holders[
                    page_number - 1 :
                ]:
                    if page_number_tracking_holder.page_content is not None:
                        if (
                            first_line == page_number_tracking_holder.page_content
                            or first_line in page_number_tracking_holder.page_content
                            or first_line
                            in page_number_tracking_holder.page_content.replace(
                                "\n", " "
                            )
                        ):
                            logging.info(
                                "Assigning page number %i to chunk",
                                page_number,
                            )
                            page_number = page_number_tracking_holder.page_number
                            break
            chunk.page_number = page_number
        return chunks


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
        chunks = await text_chunker.chunk(record["data"]["content"])

        if "page_number_tracking_holders" in record["data"]:
            page_number_tracking_holders = [
                PageNumberTrackingHolder(**sentence)
                for sentence in record["data"]["page_number_tracking_holders"]
            ]

            logging.info(f"Per page holders: {page_number_tracking_holders}")

            chunks = text_chunker.assign_page_number_to_chunks(
                chunks, page_number_tracking_holders
            )

        cleaned_record["data"]["chunks"] = [
            chunk.model_dump(by_alias=True) for chunk in chunks
        ]

    except Exception as e:
        logging.error("Chunking Error: %s", e)
        return {
            "recordId": record["recordId"],
            "data": None,
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
