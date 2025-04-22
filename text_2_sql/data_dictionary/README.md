# Data Dictionary

## Schema Store JSON

To power the knowledge of the LLM, a data dictionary containing all the SQL views / table metadata is used. Whilst the LLM could query the database at runtime to find out the schemas for the database, storing them in a text file reduces the overall latency of the system and allows the metadata for each table to be adjusted in a form of prompt engineering.

Below is a sample entry for a view / table that we which to expose to the LLM. The Microsoft SQL Server [Adventure Works Database](https://learn.microsoft.com/en-us/sql/samples/adventureworks-install-configure?view=sql-server-ver16) is used as an sample.

```json
{
    "Entity": "SalesOrderDetail",
    "Definition": null,
    "Schema": "SalesLT",
    "EntityName": null,
    "Database": "text2sql-adventure-works",
    "EntityRelationships": [
        {
            "ForeignEntity": "Product",
            "ForeignSchema": "SalesLT",
            "ForeignKeys": [
                {
                    "Column": "ProductID",
                    "ForeignColumn": "ProductID"
                }
            ],
            "ForeignDatabase": "text2sql-adventure-works",
            "FQN": "text2sql-adventure-works.SalesLT.SalesOrderDetail",
            "ForeignFQN": "text2sql-adventure-works.SalesLT.Product"
        },
        {
            "ForeignEntity": "SalesOrderHeader",
            "ForeignSchema": "SalesLT",
            "ForeignKeys": [
                {
                    "Column": "SalesOrderID",
                    "ForeignColumn": "SalesOrderID"
                }
            ],
            "ForeignDatabase": "text2sql-adventure-works",
            "FQN": "text2sql-adventure-works.SalesLT.SalesOrderDetail",
            "ForeignFQN": "text2sql-adventure-works.SalesLT.SalesOrderHeader"
        }
    ],
    "CompleteEntityRelationshipsGraph": [
        "text2sql-adventure-works.SalesLT.SalesOrderDetail -> text2sql-adventure-works.SalesLT.Product -> text2sql-adventure-works.SalesLT.ProductCategory -> Product",
        "text2sql-adventure-works.SalesLT.SalesOrderDetail -> text2sql-adventure-works.SalesLT.Product -> text2sql-adventure-works.SalesLT.ProductModel -> Product",
        "text2sql-adventure-works.SalesLT.SalesOrderDetail -> text2sql-adventure-works.SalesLT.Product -> text2sql-adventure-works.SalesLT.ProductModel -> text2sql-adventure-works.SalesLT.ProductModelProductDescription -> text2sql-adventure-works.SalesLT.ProductDescription -> ProductModelProductDescription",
        "text2sql-adventure-works.SalesLT.SalesOrderDetail -> text2sql-adventure-works.SalesLT.SalesOrderHeader -> SalesOrderDetail",
        "text2sql-adventure-works.SalesLT.SalesOrderDetail -> text2sql-adventure-works.SalesLT.SalesOrderHeader -> text2sql-adventure-works.SalesLT.Address -> CustomerAddress",
        "text2sql-adventure-works.SalesLT.SalesOrderDetail -> text2sql-adventure-works.SalesLT.SalesOrderHeader -> text2sql-adventure-works.SalesLT.Customer -> CustomerAddress"
    ],
    "Columns": [
        {
            "Name": "SalesOrderID",
            "DataType": "int",
            "Definition": null,
            "SampleValues": [
                71898,
                71831,
                71899,
                71796,
                71946
            ]
        },
        {
            "Name": "SalesOrderDetailID",
            "DataType": "int",
            "Definition": null,
            "SampleValues": [
                110691,
                113288,
                112940,
                112979,
                111078
            ]
        },
        {
            "Name": "OrderQty",
            "DataType": "smallint",
            "Definition": null,
            "SampleValues": [
                15,
                23,
                16,
                7,
                5
            ]
        },
        {
            "Name": "ProductID",
            "DataType": "int",
            "Definition": null,
            "SampleValues": [
                889,
                780,
                793,
                795,
                974
            ]
        },
        {
            "Name": "UnitPrice",
            "DataType": "money",
            "Definition": null,
            "SampleValues": [
                "602.3460",
                "32.9940",
                "323.9940",
                "149.8740",
                "20.2942"
            ]
        },
        {
            "Name": "UnitPriceDiscount",
            "DataType": "money",
            "Definition": null,
            "SampleValues": [
                "0.4000",
                "0.1000",
                "0.0500",
                "0.0200",
                "0.0000"
            ]
        },
        {
            "Name": "LineTotal",
            "DataType": "numeric",
            "Definition": null,
            "SampleValues": [
                "66.428908",
                "2041.188000",
                "64.788000",
                "1427.592000",
                "5102.970000"
            ]
        },
        {
            "Name": "rowguid",
            "DataType": "uniqueidentifier",
            "Definition": null,
            "SampleValues": [
                "09E7A695-3260-483E-91F8-A980441B9DD6",
                "C9FCF326-D1B9-44A4-B29D-2D1888F6B0FD",
                "5CA4F84A-BAFE-485C-B7AD-897F741F76CE",
                "E11CF974-4DCC-4A5C-98C3-2DE92DD2A15D",
                "E7C11996-8D83-4515-BFBD-7E380CDB6252"
            ]
        },
        {
            "Name": "ModifiedDate",
            "DataType": "datetime",
            "Definition": null,
            "SampleValues": [
                "2008-06-01 00:00:00"
            ]
        }
    ],
    "FQN": "text2sql-adventure-works.SalesLT.SalesOrderDetail"
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

## Column Value Store JSONL

To aid LLM understand, the dimension tables within a star schema are indexed if they contain 'string' based values. This allows the LLM to use search to understand the context of the question asked. e.g. If a user asks 'What are the total sales on VE-C304-S', we can use search to determine that 'VE-C304-S' is in fact a Product Number and which entity it belongs to.

This avoids having to index the fact tables, saving storage, and allows us to still use the SQL queries to slice and dice the data accordingly.

```json
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "WB-H098", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "VE-C304-S", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "VE-C304-M", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "VE-C304-L", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TT-T092", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TT-R982", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TT-M928", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-T723", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-R982", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-R628", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-R092", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-M823", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-M602", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TI-M267", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TG-W091-S", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TG-W091-M", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "TG-W091-L", "Synonyms": []}
{"Entity": "Product", "Schema": "SalesLT", "Database": "text2sql-adventure-works", "FQN": "text2sql-adventure-works.SalesLT.Product.ProductNumber", "Column": "ProductNumber", "Value": "ST-1401", "Synonyms": []}
```

## Indexing

`./deploy_ai_search_indexes/text_2_sql.py` & `./deploy_ai_search_indexes/text_2_sql_query_cache.py` contains the scripts to deploy and index the data dictionary for use within the plugin. See instructions in `./deploy_ai_search_indexes/README.md`. There is **no automatic mechanism** to upload these .json files currently to a storage account, once generated, you must automatically upload them to the appropriate storage account that the indexer is connected to.

## Automatic Generation

Manually creating the `entities.json` is a time consuming exercise. To speed up generation, a mixture of SQL Queries and an LLM can be used to generate a initial version. Existing comments and descriptions in the database, can be combined with sample values to generate the necessary descriptions. Manual input can then be used to tweak it for the use case and any improvements.

`./text_2_sql_core/data_dictionary/data_dictionary_creator.py` contains a utility class that handles the automatic generation and selection of schemas from the source SQL database. It must be subclassed to the appropriate engine to handle engine specific queries and connection details.

See `./generated_samples/` for an example output of the script. This can then be automatically indexed with the provided indexer for the **Vector-Based Approach**.

The following Databases have pre-built scripts for them:

- **Databricks:** `./text_2_sql_core/data_dictionary/databricks_data_dictionary_creator.py`
- **Snowflake:** `./text_2_sql_core/data_dictionary/snowflake_data_dictionary_creator.py`
- **TSQL:** `./text_2_sql_core/data_dictionary/tsql_data_dictionary_creator.py`
- **Postgres:** `./text_2_sql_core/data_dictionary/postgres_data_dictionary_creator.py`

If there is no pre-built script for your database engine, take one of the above as a starting point and adjust it.

## Running

To generate a data dictionary, perform the following steps:

1. Create your `.env` file based on the provided sample `text_2_sql/.env.example`. Place this file in the same place in `text_2_sql/.env`.

**Execute the following commands in the `text_2_sql_core` directory:**

2. Package and install the `text_2_sql_core` library. See [build](https://docs.astral.sh/uv/concepts/projects/build/) if you want to build as a wheel and install on an agent. Or you can run from within a `uv` environment and skip packaging.
    - Install the optional dependencies if you need a database connector other than TSQL. `uv sync --extra <DATABASE ENGINE>`

3. Run `uv run data_dictionary <DATABASE ENGINE>`
    - You can pass the following command line arguements:
        - `-- output_directory` or `-o`: Optional directory that the script will write the output files to.
        - `-- single_file` or `-s`: Optional flag that writes all schemas to a single file.
        - `-- generate_definitions` or `-gen`: Optional flag that uses OpenAI to generate descriptions.
    - If you need control over the following, run the file directly:
        - `entities`: A list of entities to extract. Defaults to None.
        - `excluded_entities`: A list of entities to exclude.
        - `excluded_schemas`: A list of schemas to exclude.

4. Upload these generated data dictionaries files to the relevant containers in your storage account. Wait for them to be automatically indexed with the included skillsets.

> [!IMPORTANT]
>
> - The data dictionary generation scripts will output column values for all possible filter clauses. This could lead to output of sensitive information. You should add exclusion criteria to exclude these for only columns that you may want to filter by.
