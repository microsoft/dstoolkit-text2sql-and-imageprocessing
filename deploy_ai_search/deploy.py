# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import argparse
from rag_documents import RagDocumentsAISearch


def deploy_config(arguments: argparse.Namespace):
    """Deploy the indexer configuration based on the arguments passed.

    Args:
        arguments (argparse.Namespace): The arguments passed to the script"""
    if arguments.indexer_type == "rag":
        index_config = RagDocumentsAISearch(
            suffix=arguments.suffix,
            rebuild=arguments.rebuild,
            enable_page_by_chunking=arguments.enable_page_chunking,
        )
    else:
        raise ValueError("Invalid Indexer Type")

    index_config.deploy()

    if arguments.rebuild:
        index_config.reset_indexer()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some arguments.")
    parser.add_argument(
        "--indexer_type",
        type=str,
        required=True,
        help="Type of Indexer want to deploy.",
    )
    parser.add_argument(
        "--rebuild",
        type=bool,
        required=False,
        help="Whether want to delete and rebuild the index",
    )
    parser.add_argument(
        "--enable_page_chunking",
        type=bool,
        required=False,
        help="Whether want to enable chunking by page in adi skill, if no value is passed considered False",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        required=False,
        help="Suffix to be attached to indexer objects",
    )

    args = parser.parse_args()
    deploy_config(args)
