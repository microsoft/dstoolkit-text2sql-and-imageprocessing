# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
)

def create_text_2_sql_schema_cache_index(name: str) -> SearchIndex:
    """Creates the Text2SQL Schema Cache index definition.
    
    Args:
        name: Name of the index
        
    Returns:
        SearchIndex: The index definition
    """
    
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="Id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="DatabasePath", type=SearchFieldDataType.String),
            SimpleField(name="Entity", type=SearchFieldDataType.String),
            SimpleField(name="Schema", type=SearchFieldDataType.String),
            SimpleField(name="SchemaData", type=SearchFieldDataType.String),
            SimpleField(name="LastUpdated", type=SearchFieldDataType.DateTimeOffset),
        ],
    )
