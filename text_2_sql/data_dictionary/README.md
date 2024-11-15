# Data Dictionary

## entities.json

To power the knowledge of the LLM, a data dictionary containing all the SQL views / table metadata is used. Whilst the LLM could query the database at runtime to find out the schemas for the database, storing them in a text file reduces the overall latency of the system and allows the metadata for each table to be adjusted in a form of prompt engineering.

Below is a sample entry for a view / table that we which to expose to the LLM. The Microsoft SQL Server [Adventure Works Database](https://learn.microsoft.com/en-us/sql/samples/adventureworks-install-configure?view=sql-server-ver16) is used as an sample.

```json
{
    "Entity": "SalesLT.SalesOrderDetail",
    "Definition": "The SalesLT.SalesOrderDetail entity contains detailed information about individual items within sales orders. This entity includes data on the sales order ID, the specific details of each order item such as quantity, product ID, unit price, and any discounts applied. It also includes calculated fields such as the line total for each order item. This entity can be used to answer questions related to the specifics of sales transactions, such as which products were purchased in each order, the quantity of each product ordered, and the total price of each order item.",
    "EntityName": "Sales Line Items Information",
    "Database": "AdventureWorksLT",
    "Warehouse": null,
    "EntityRelationships": [
        {
            "ForeignEntity": "SalesLT.Product",
            "ForeignKeys": [
                {
                    "Column": "ProductID",
                    "ForeignColumn": "ProductID"
                }
            ]
        },
        {
            "ForeignEntity": "SalesLT.SalesOrderHeader",
            "ForeignKeys": [
                {
                    "Column": "SalesOrderID",
                    "ForeignColumn": "SalesOrderID"
                }
            ]
        }
    ],
    "CompleteEntityRelationshipsGraph": [
        "SalesLT.SalesOrderDetail -> SalesLT.Product -> SalesLT.ProductCategory",
        "SalesLT.SalesOrderDetail -> SalesLT.Product -> SalesLT.ProductModel -> SalesLT.ProductModelProductDescription -> SalesLT.ProductDescription",
        "SalesLT.SalesOrderDetail -> SalesLT.SalesOrderHeader -> SalesLT.Address -> SalesLT.CustomerAddress -> SalesLT.Customer",
        "SalesLT.SalesOrderDetail -> SalesLT.SalesOrderHeader -> SalesLT.Customer -> SalesLT.CustomerAddress -> SalesLT.Address"
    ],
    "Columns": [
        {
            "Name": "SalesOrderID",
            "DataType": "int",
            "Definition": "The SalesOrderID column in the SalesLT.SalesOrderDetail entity contains unique numerical identifiers for each sales order. Each value represents a specific sales order, ensuring that each order can be individually referenced and tracked. The values are in a sequential numeric format, indicating the progression and uniqueness of each sales transaction within the database.",
            "AllowedValues": null,
            "SampleValues": [
                71938,
                71784,
                71935,
                71923,
                71946
            ]
        },
        {
            "Name": "SalesOrderDetailID",
            "DataType": "int",
            "Definition": "The SalesOrderDetailID column in the SalesLT.SalesOrderDetail entity contains unique identifier values for each sales order detail record. The values are numeric and are used to distinguish each order detail entry within the database. These identifiers are essential for maintaining data integrity and enabling efficient querying and data manipulation within the sales order system.",
            "AllowedValues": null,
            "SampleValues": [
                110735,
                113231,
                110686,
                113257,
                113307
            ]
        }
    ]
}
```

## Property Definitions
- **EntityName** is a human readable name for the entity.
- **Entity** is the actual name for the entity that is used in the SQL query.
- **Definition** provides a comprehensive description of what information the entity contains.
- **Columns** contains a list of the columns exposed for querying. Each column contains:
    - **Definition** a short definition of what information the column contains. Here you can add extra metadata to **prompt engineer** the LLM to select the right columns or interpret the data in the column correctly.
    - **Name** is the actual column name.
    - **DataType** is the datatype for the column.
    - **SampleValues (optional)** is a list of sample values that are in the column. This is useful for instructing the LLM of what format the data may be in.
    - **AllowedValues (optional)** is a list of absolute allowed values for the column. This instructs the LLM only to use these values if filtering against this column.
- **EntityRelationships** contains mapping of the immediate relationships to this entity. Contains details of the foreign keys to join against.
- **CompleteEntityRelationshipsGraph** contains a directed graph of how this entity relates to all others in the database. The LLM can use this to work out the joins to make.

A full data dictionary must be built for all the views / tables you which to expose to the LLM. The metadata provide directly influences the accuracy of the Text2SQL component.

## Indexing

`./deploy_ai_search/text_2_sql.py` & `./deploy_ai_search/text_2_sql_query_cache.py` contains the scripts to deploy and index the data dictionary for use within the plugin. See instructions in `./deploy_ai_search/README.md`.

## Automatic Generation

Manually creating the `entities.json` is a time consuming exercise. To speed up generation, a mixture of SQL Queries and an LLM can be used to generate a initial version. Existing comments and descriptions in the database, can be combined with sample values to generate the necessary descriptions. Manual input can then be used to tweak it for the use case and any improvements.

`data_dictionary_creator.py` contains a utility class that handles the automatic generation and selection of schemas from the source SQL database. It must be subclassed to the appropriate engine.

`sql_server_data_dictionary_creator.py` contains a subclassed version of `data_dictionary_creator.py` that implements the SQL Server specific functionality to extract the entities.

See `./generated_samples/` for an example output of the script. This can then be automatically indexed with the provided indexer for the **Vector-Based Approach**.
