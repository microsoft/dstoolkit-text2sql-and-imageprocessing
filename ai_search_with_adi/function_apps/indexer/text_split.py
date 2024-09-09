# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import spacy
import logging
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import json
from sklearn.metrics.pairwise import cosine_similarity

nlp = spacy.load("en_core_web_md")


class RecursiveCharacterTextSplitter:
    def __init__(self, fragment_size=100, division_chars=["\n\n", "\n", " ", ""]):
        self.fragment_size = fragment_size
        self.division_chars = division_chars

    def split_text(self, text):
        return self._recursive_split(text, 0)

    def _recursive_split(self, text, char_idx):
        if len(text) <= self.fragment_size or char_idx >= len(self.division_chars):
            return [text]

        char = self.division_chars[char_idx]
        fragments = text.split(char)
        result = []
        current_fragment = ""

        for fragment in fragments:
            if len(current_fragment) + len(fragment) + len(char) <= self.fragment_size:
                current_fragment += char + fragment
            else:
                if current_fragment:
                    result.append(current_fragment)
                current_fragment = fragment

        if current_fragment:
            result.append(current_fragment)

        if any(len(frag) > self.fragment_size for frag in result):
            return self._recursive_split(text, char_idx + 1)

        return result


class CharacterTextSplitter:
    def __init__(self, fragment_size=100, separator=" "):
        self.fragment_size = fragment_size
        self.separator = separator

    def split_text(self, text):
        fragments = text.split(self.separator)
        result = []
        current_fragment = ""

        for fragment in fragments:
            if (
                len(current_fragment) + len(fragment) + len(self.separator)
                <= self.fragment_size
            ):
                current_fragment += self.separator + fragment
            else:
                if current_fragment:
                    result.append(current_fragment)
                current_fragment = fragment

        if current_fragment:
            result.append(current_fragment)

        return result


class RecursiveTextSplitter:
    def __init__(self, fragment_size=100, division_tokens=["\n\n", "\n", " ", ""]):
        self.fragment_size = fragment_size
        self.division_tokens = division_tokens

    def split_text(self, text):
        return self._recursive_split(text, 0)

    def _recursive_split(self, text, token_idx):
        if len(text) <= self.fragment_size or token_idx >= len(self.division_tokens):
            return [text]

        token = self.division_tokens[token_idx]
        fragments = text.split(token)
        result = []
        current_fragment = ""

        for fragment in fragments:
            if len(current_fragment) + len(fragment) + len(token) <= self.fragment_size:
                current_fragment += token + fragment
            else:
                if current_fragment:
                    result.append(current_fragment)
                current_fragment = fragment

        if current_fragment:
            result.append(current_fragment)

        if any(len(frag) > self.fragment_size for frag in result):
            return self._recursive_split(text, token_idx + 1)

        return result


class SemanticDoubleMergingSplitterNodeParser:
    def __init__(
        self,
        initial_threshold=0.8,
        appending_threshold=0.7,
        merging_threshold=0.75,
        fragment_size=100,
        spacy_model="en_core_web_md",
    ):
        self.initial_threshold = initial_threshold
        self.appending_threshold = appending_threshold
        self.merging_threshold = merging_threshold
        self.fragment_size = fragment_size
        try:
            self.nlp = spacy.load(spacy_model)
        except IOError:
            raise ValueError(
                f"Spacy model '{spacy_model}' not found. Please download it using 'python -m spacy download {spacy_model}'"
            )

    def split_text(self, text):
        sentences = self._split_into_sentences(text)
        initial_chunks = self._initial_pass(sentences)
        final_chunks = self._second_pass(initial_chunks)
        return final_chunks

    def _split_into_sentences(self, text):
        doc = self.nlp(text)
        sentences = [sent.text for sent in doc.sents]
        return sentences

    def _initial_pass(self, sentences):
        chunks = []
        current_chunk = []

        i = 0
        while i < len(sentences):
            current_chunk.append(sentences[i])
            if len(current_chunk) >= 2:
                cosine_sim = self._cosine_similarity(
                    " ".join(current_chunk[-2:]), sentences[i]
                )
                if (
                    cosine_sim < self.initial_threshold
                    or len(" ".join(current_chunk)) > self.fragment_size
                ):
                    if len(current_chunk) > 2:
                        chunks.append(" ".join(current_chunk[:-1]))
                        current_chunk = [current_chunk[-1]]
                    else:
                        chunks.append(current_chunk[0])
                        current_chunk = [current_chunk[1]]
            i += 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _second_pass(self, chunks):
        merged_chunks = []
        current_chunk = chunks[0]

        i = 1
        while i < len(chunks):
            cosine_sim = self._cosine_similarity(current_chunk, chunks[i])
            if (
                cosine_sim >= self.merging_threshold
                and len(current_chunk + " " + chunks[i]) <= self.fragment_size
            ):
                current_chunk += " " + chunks[i]
            else:
                merged_chunks.append(current_chunk)
                current_chunk = chunks[i]
            i += 1

        merged_chunks.append(current_chunk)
        return merged_chunks

    def _cosine_similarity(self, text1, text2):
        vec1 = self.nlp(text1).vector
        vec2 = self.nlp(text2).vector
        return cosine_similarity([vec1], [vec2])[0, 0]


class FlanT5Chunker:
    def __init__(
        self, model_name="chentong00/propositionizer-wiki-flan-t5-large", device="cpu"
    ):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)
        self.device = device
        self.max_length = 512  # Model's maximum token length

    def flan_t5_chunking(self, text, chunk_size=500, stride=20):
        input_text = f"Title: . Section: . Content: {text}"
        input_ids = self.tokenizer(input_text, return_tensors="pt").input_ids.to(
            self.device
        )
        total_length = input_ids.shape[1]

        chunks = []
        for i in range(0, total_length, chunk_size - stride):
            end = min(i + chunk_size, total_length)
            chunk_input_ids = input_ids[:, i:end]
            outputs = self.model.generate(
                chunk_input_ids, max_new_tokens=self.max_length
            ).cpu()
            output_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            try:
                prop_list = json.loads(output_text)
            except json.JSONDecodeError:
                prop_list = []
                print("[ERROR] Failed to parse output text as JSON.")
            chunks.append(prop_list)

        # Flatten the list of lists
        return [item for sublist in chunks for item in sublist]


def clean_input(value):
    """Clean the input value.

    Args:
        value: The input value.

    Returns:
        The cleaned value."""
    if isinstance(value, str):
        return value.strip('"')
    return value


async def process_text_split(record: dict, text_split_config: dict) -> dict:
    """Process the text split request.

    Args:
        record (dict): The request record.
        text_split_config (dict): The headers for config.

    Returns:
        dict: The response record.
    """
    try:
        data = record["data"]
        text = clean_input(data.get("text"))
        logging.info(f"Request Body: {record}")
    except KeyError:
        return {
            "recordId": record["recordId"],
            "data": {},
            "errors": [
                {
                    "message": "Failed to split text. Pass valid parameters.",
                }
            ],
            "warnings": None,
        }
    else:
        if text is None:
            logging.error("Failed to split text. Pass valid text.")
            return {
                "recordId": record["recordId"],
                "data": {},
                "errors": [
                    {
                        "message": "Failed to split text. Pass valid text.",
                    }
                ],
                "warnings": None,
            }

        splitter_type = clean_input(
            text_split_config.get("text_split_mode", "recursive_character")
        )
        fragment_size = float(
            clean_input(text_split_config.get("maximum_page_length", 100))
        )
        separator = clean_input(text_split_config.get("separator", " "))
        initial_threshold = float(
            clean_input(text_split_config.get("initial_threshold", 0.8))
        )
        appending_threshold = float(
            clean_input(text_split_config.get("appending_threshold", 0.7))
        )
        merging_threshold = float(
            clean_input(text_split_config.get("merging_threshold", 0.75))
        )

        try:
            if splitter_type == "recursive_character":
                splitter = RecursiveCharacterTextSplitter(fragment_size=fragment_size)
            elif splitter_type == "character":
                splitter = CharacterTextSplitter(
                    fragment_size=fragment_size, separator=separator
                )
            elif splitter_type == "recursive":
                splitter = RecursiveTextSplitter(fragment_size=fragment_size)
            elif splitter_type == "semantic":
                splitter = SemanticDoubleMergingSplitterNodeParser(
                    initial_threshold=initial_threshold,
                    appending_threshold=appending_threshold,
                    merging_threshold=merging_threshold,
                    fragment_size=fragment_size,
                )
            elif splitter_type == "flan_t5":
                splitter = FlanT5Chunker()
            else:
                logging.error("Failed to split text. Pass valid splitter type.")
                logging.error(f"Splitter Type: {splitter_type}")
                return {
                    "recordId": record["recordId"],
                    "data": {},
                    "errors": [
                        {
                            "message": "Failed to split text. Pass valid splitter type.",
                        }
                    ],
                    "warnings": None,
                }

            if splitter_type == "flan_t5":
                chunks = splitter.flan_t5_chunking(text)
            else:
                chunks = splitter.split_text(text)
        except Exception as e:
            logging.error(f"Error during splitting: {e}")

            return {
                "recordId": record["recordId"],
                "data": {},
                "errors": [
                    {
                        "message": f"Failed to split text. Check function app logs for more details of exact failure. {str(e)}",
                    }
                ],
                "warnings": None,
            }

        else:
            return {
                "recordId": record["recordId"],
                "data": {
                    "chunks": chunks,
                },
                "errors": None,
                "warnings": None,
            }
