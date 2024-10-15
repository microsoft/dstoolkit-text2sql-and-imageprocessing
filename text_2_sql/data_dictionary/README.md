# Data Dictionary

## entities.json

To power the knowledge of the LLM, a data dictionary containing all the SQL views / table metadata is used. Whilst the LLM could query the database at runtime to find out the schemas for the database, storing them in a text file reduces the overall latency of the system and allows the metadata for each table to be adjusted in a form of prompt engineering.

Below is a sample entry for a view / table that we which to expose to the LLM. The Microsoft SQL Server [Adventure Works Database](https://learn.microsoft.com/en-us/sql/samples/adventureworks-install-configure?view=sql-server-ver16) is used as an sample.

```json
{
    "EntityName": "Get All Categories",
    "Entity": "vGetAllCategories",
    "Description": "This view provides a comprehensive list of all product categories and their corresponding subcategories in the SalesLT schema of the AdventureWorksLT database. It is used to understand the hierarchical structure of product categories, facilitating product organization and categorization.",
    "Columns": [
        {
            "Definition": "A unique identifier for each product category. This ID is used to reference specific categories.",
            "Name": "ProductCategoryID",
            "Type": "INT"
        },
        {
            "Definition": "The name of the parent product category. This represents the top-level category under which subcategories are grouped.",
            "Name": "ParentProductCategoryName",
            "Type": "NVARCHAR(50)"
        },
        {
            "Definition": "The name of the product category. This can refer to either a top-level category or a subcategory, depending on the context.",
            "Name": "ProductCategoryName",
            "Type": "NVARCHAR(50)"
        }
    ]
}
```

## Property Definitions
- **EntityName** is a human readable name for the entity.
- **Entity** is the actual name for the entity that is used in the SQL query.
- **Description** provides a comprehensive description of what information the entity contains.
- **Columns** contains a list of the columns exposed for querying. Each column contains:
    - **Definition** a short definition of what information the column contains. Here you can add extra metadata to **prompt engineer** the LLM to select the right columns or interpret the data in the column correctly.
    - **Name** is the actual column name.
    - **Type** is the datatype for the column.
    - **SampleValues (optional)** is a list of sample values that are in the column. This is useful for instructing the LLM of what format the data may be in.
    - **AllowedValues (optional)** is a list of absolute allowed values for the column. This instructs the LLM only to use these values if filtering against this column.

A full data dictionary must be built for all the views / tables you which to expose to the LLM. The metadata provide directly influences the accuracy of the Text2SQL component.

## Indexing

`./deploy_ai_search/text_2_sql.py` & `./deploy_ai_search/text_2_sql_query_cache.py` contains the scripts to deploy and index the data dictionary for use within the plugin. See instructions in `./deploy_ai_search/README.md`.

## Automatic Generation

Manually creating the `entities.json` is a time consuming exercise. To speed up generation, a mixture of SQL Queries and an LLM can be used to generate a initial version. Existing comments and descriptions in the database, can be combined with sample values to generate the necessary descriptions. Manual input can then be used to tweak it for the use case and any improvements.

`data_dictionary_creator.py` contains a utility class that handles the automatic generation and selection of schemas from the source SQL database. It must be subclassed to the appropriate engine.

`sql_server_data_dictionary_creator.py` contains a subclassed version of `data_dictionary_creator.py` that implements the SQL Server specific functionality to extract the entities.

See `./generated_samples/` for an example output of the script. This can then be automatically indexed with the provided indexer for the **Vector-Based Approach**.
