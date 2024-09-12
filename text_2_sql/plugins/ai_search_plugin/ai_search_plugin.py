# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from semantic_kernel.functions import kernel_function
from typing import Annotated
import os
import json
import logging
from ai_search import run_ai_search_query


class AISearchPlugin:
    """A plugin that allows for the execution of AI Search queries against a text input."""

    @staticmethod
    def system_prompt() -> str:
        """Get the system prompt for the AI Search Plugin."""
        return """Use the AI Search to return documents that have been indexed, that might be relevant for a piece of text to aid understanding. AI Search should always be used, even if you believe it might not be relevant. Execute this in parallel to any other functions that might be relevant."""

    @kernel_function(
        description="Runs an hybrid semantic search against some text to return relevant documents that are indexed within AI Search.",
        name="QueryDocumentStorage",
    )
    async def query_document_storage(
        self, text: Annotated[str, "The text to run a semantic search against."]
    ) -> str:
        """Sends an text query to AI Search and uses Semantic Ranking to return a result.

        Args:
        ----
            text (str): The text to run the search against.

        Returns:
        ----
            str: The JSON representation of the search results.
        """

        documents = await run_ai_search_query(
            text,
            ["ChunkEmbedding"],
            ["Title", "Chunk", "SourceUri"],
            os.environ["AIService__AzureSearchOptions__RagDocuments__Index"],
            os.environ["AIService__AzureSearchOptions__RagDocuments__SemanticConfig"],
        )

        logging.debug("Results: %s", documents)
        return json.dumps(documents, default=str)
