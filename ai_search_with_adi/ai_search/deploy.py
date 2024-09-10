# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
from ai_search_with_adi.ai_search.environment import (
    get_search_endpoint,
    get_managed_identity_id,
    get_search_key,
    get_key_vault_url,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from ai_search_with_adi.ai_search.rag_documents import RagDocumentsAISearch


def main(args):
    endpoint = get_search_endpoint()

    try:
        credential = DefaultAzureCredential(
            managed_identity_client_id=get_managed_identity_id()
        )
        # initializing key vault client
        client = SecretClient(vault_url=get_key_vault_url(), credential=credential)
        print("Using managed identity credential")
    except Exception as e:
        print(e)
        credential = AzureKeyCredential(get_search_key(client=client))
        print("Using Azure Key credential")

    if args.indexer_type == "rag":
        # Deploy the inquiry index
        index_config = RagDocumentsAISearch(
            endpoint=endpoint,
            credential=credential,
            suffix=args.suffix,
            rebuild=args.rebuild,
            enable_page_by_chunking=args.enable_page_chunking,
        )
    else:
        raise ValueError("Invalid Indexer Type")

    index_config.deploy()

    if args.rebuild:
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
    main(args)
