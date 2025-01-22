# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import argparse
from image_processing import ImageProcessingAISearch
from text_2_sql_schema_store import Text2SqlSchemaStoreAISearch
from text_2_sql_query_cache import Text2SqlQueryCacheAISearch
from text_2_sql_column_value_store import Text2SqlColumnValueStoreAISearch
import logging

logging.basicConfig(level=logging.INFO)


def deploy_config(arguments: argparse.Namespace):
    """Deploy the indexer configuration based on the arguments passed.

    Args:
        arguments (argparse.Namespace): The arguments passed to the script"""

    suffix = None if arguments.suffix == "None" else arguments.suffix
    if arguments.index_type == "image_processing":
        index_config = ImageProcessingAISearch(
            suffix=suffix,
            rebuild=arguments.rebuild,
            enable_page_by_chunking=arguments.enable_page_wise_chunking,
        )
    elif arguments.index_type == "text_2_sql_schema_store":
        index_config = Text2SqlSchemaStoreAISearch(
            suffix=suffix,
            rebuild=arguments.rebuild,
            single_data_dictionary_file=arguments.single_data_dictionary_file,
        )
    elif arguments.index_type == "text_2_sql_query_cache":
        index_config = Text2SqlQueryCacheAISearch(
            suffix=suffix,
            rebuild=arguments.rebuild,
            single_query_cache_file=arguments.single_query_cache_file,
            enable_query_cache_indexer=arguments.enable_query_cache_indexer,
        )
    elif arguments.index_type == "text_2_sql_column_value_store":
        index_config = Text2SqlColumnValueStoreAISearch(
            suffix=suffix,
            rebuild=arguments.rebuild,
        )
    else:
        raise ValueError("Invalid Indexer Type")

    index_config.deploy()

    if arguments.rebuild:
        index_config.reset_indexer()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some arguments.")
    parser.add_argument(
        "--index_type",
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
        "--enable_page_wise_chunking",
        type=bool,
        required=False,
        help="Whether want to enable chunking by page in adi skill, if no value is passed considered False",
    )
    parser.add_argument(
        "--single_data_dictionary_file",
        type=bool,
        required=False,
        help="Whether or not a single data dictionary file should be uploaded, or one per entity",
    )
    parser.add_argument(
        "--single_query_cache_file",
        type=bool,
        required=False,
        help="Whether or not a single cache file should be uploaded, or one per question",
    )
    parser.add_argument(
        "--enable_query_cache_indexer",
        type=bool,
        required=False,
        help="Whether or not the sql query cache indexer should be enabled",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        required=False,
        help="Suffix to be attached to indexer objects",
    )

    args = parser.parse_args()
    deploy_config(args)
