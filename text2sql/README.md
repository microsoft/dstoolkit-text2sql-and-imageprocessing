# Multi-Shot Text2SQL Component

This portion of the repo contains code to implement a multi-shot approach to Text2SQL generation. This code can be integrated into a RAG application to allow the application to intelligently switch between different data sources (SQL, AI Search etc) to answer the question with the best possible information.

The implementation is written for [Semantic Kernel](https://github.com/microsoft/semantic-kernel) in Python, although it can easily be adapted for C# or another framework such as LangChain.

The sample provided works with Azure SQL Server, although it has been easily adapted to other SQL sources such as Snowflake.

## Why Text2SQL instead of indexing the database contents?

Generating SQL queries and executing them to provide context for the RAG application provided several benefits in the use case this was designed for.

- Automatic report generation did not have to be built to automatically index the contents of the database and chunk it accordingly.
- By retaining the original table structure rather than indexing the contents, we are able to perform aggregations and calculations on the data quickly and accurately to answer numerical or statistic based questions. On a pure document based system, some of these questions are not easily answerable without pre-computing reports or extracting all the content
    - e.g. *What is our top performing sales per by quantity of units sold this month? What item did they sell the most of?* is answerable with a few simple SQL query if the correct views are exposed.
    - Without Text2SQL, a document needs to contain the top sales information for each month and be updated regularly. Additionally, we need to then store in a document all the relevant information for what they have sold that month and add into the chunk information that they are the top performing sales person.
- Pushing numerical calculations onto the source SQL engine ensures accuracy in the maths.
- Data can be updated real-time in the source database and be immediately accessible to the LLM.

## Multi-Shot Approach

A common way to perform Text2SQL generation is to provide the complete schema information (either a full schema or a plain text description) inside the initial prompt. Whilst this works for small databases, there are issues with scalability as the number of tables and views exposed to the LLM increases:

- More tables / views significantly increases the number of tokens used within the prompt and the cost of inference.
- More schema information can cause confusion with the LLM. In our original use case, when exceeding 5 complex tables / views, we found that the LLM could get confused between which columns belonged to which entity and as such, would generate invalid SQL queries.

To solve these issues, a Multi-Shot approach is used:

![Comparison between a common Text2SQL approach and a Multi-Shot Text2SQL approach.](./images/OneShot%20SQL%20vs%20TwoShot%20SQL%20OpenAI.png "Multi Shot SQL Approach")

Instead of inserting the entire database schema into the prompt, a brief description of the available entities is injected into the prompt. This limits the number of tokens used and avoids filling the prompt with confusing schema information.

Using Auto-Function calling capabilities, the LLM is able to retrieve from the plugin the full schema information for the views / tables that it considers useful for answering the question. Once retrieved, the full SQL query can then be generated. The schemas for multiple views / tables can be retrieved to allow the LLM to perform joins and other complex queries.

## Provided Notebooks

- `./rag_with_text_2_sql.ipynb` provides example of how to utilise the Text2SQL plugin to query the database.
- `./rag_with_ai_searchandtext_2_sql.ipynb` provides an example of how to use the Text2SQL and an AISearch plugin in parallel to automatically retrieve data from the most relevant source to answer the query.
    - This setup is useful for a production application as the SQL Database is unlikely to be able to answer all the questions a user may ask.

## SQL Plugin

`./plugins/sql_plugin` contains all the relevant Semantic Kernel code for the plugin.

### entities.json

To power the knowledge of the LLM, a data dictionary containing all the SQL views / table metadata is used. Whilst the LLM could query the database at runtime to find out the schemas for the database, storing them in a text file reduces the overall latency of the system and allows the metadata for each table to be adjusted in a form of prompt engineering.

The data dictionary is stored in `./plugins/sql_plugin/entities.json`. Below is a sample entry for a view / table that we which to expose to the LLM. The Microsoft SQL Server [Adventure Works Database](https://learn.microsoft.com/en-us/sql/samples/adventureworks-install-configure?view=sql-server-ver16) is used as an sample.

```json
{
    "view_name": "Get All Categories",
    "entity": "vGetAllCategories",
    "description": "This view provides a comprehensive list of all product categories and their corresponding subcategories in the SalesLT schema of the AdventureWorksLT database. It is used to understand the hierarchical structure of product categories, facilitating product organization and categorization.",
    "selector": "Use this view to retrieve information about product categories and subcategories. It is useful for scenarios where product categorization is required, such as generating reports based on product categories or filtering products by category.",
    "columns": [
        {
            "definition": "A unique identifier for each product category. This ID is used to reference specific categories.",
            "name": "ProductCategoryID",
            "type": "INT"
        },
        {
            "definition": "The name of the parent product category. This represents the top-level category under which subcategories are grouped.",
            "name": "ParentProductCategoryName",
            "type": "NVARCHAR(50)"
        },
        {
            "definition": "The name of the product category. This can refer to either a top-level category or a subcategory, depending on the context.",
            "name": "ProductCategoryName",
            "type": "NVARCHAR(50)"
        }
    ]
}
```

#### Property Definitions
- **view_name** or **table_name** is a human readable name for the entity.
- **entity** is the actual name for the entity that is used in the SQL query.
- **description** provides a comprehensive description of what information the entity contains.
- **selector** provides reasoning to the LLM of in which scenarios it should select this entity.
- **columns** contains a list of the columns exposed for querying. Each column contains:
    - **definition** a short definition of what information the column contains. Here you can add extra metadata to **prompt engineer** the LLM to select the right columns or interpret the data in the column correctly.
    - **name** is the actual column name.
    - **type** is the datatype for the column.
    - **sample_values (optional)** is a list of sample values that are in the column. This is useful for instructing the LLM of what format the data may be in.
    - **allowed_values (optional)** is a list of absolute allowed values for the column. This instructs the LLM only to use these values if filtering against this column.

A full data dictionary must be built for all the views / tables you which to expose to the LLM. The metadata provide directly influences the accuracy of the Text2SQL component.

### sql_plugin.py

The `./plugins/sql_plugin/sql_plugin.py` contains 3 key methods to power the Text2SQL engine.

#### system_prompt()

This method takes the loaded `entities.json` file and generates a system prompt based on it. Here, the **entity_name**, **description** and **selector** are used to build a list of available entities for the LLM to select.

This is then inserted into a pre-made Text2SQL generation prompt that already contains optimised and working instructions for the LLM. This system prompt for the plugin is added to the main prompt file at runtime.

The **target_engine** is passed to the prompt, along with **engine_specific_rules** to ensure that the SQL queries generated work on the target engine.

#### get_entity_schema()

This method is called by the Semantic Kernel framework automatically, when instructed to do so by the LLM, to fetch the full schema definitions for a given entity. This returns a JSON string of the chosen entity which allows the LLM to understand the column definitions and their associated metadata. This can be called in parallel for multiple entities.

#### run_sql_query()

This method is called by the Semantic Kernel framework automatically, when instructed to do so by the LLM, to run a SQL query against the given database. It returns a JSON string containing a row wise dump of the results returned. These results are then interpreted to answer the question.

## Sample Usage

### What is the top performing product by quantity of units sold?

#### SQL Query Generated

*SELECT TOP 1 ProductID, SUM(OrderQty) AS TotalUnitsSold FROM SalesLT.SalesOrderDetail GROUP BY ProductID ORDER BY TotalUnitsSold DESC*

#### JSON Result

```json
{
    "answer": "The top-performing product by quantity of units sold is the **Classic Vest, S** from the **Classic Vest** product model, with a total of 87 units sold [1][2].",
    "sources": [
        {
            "title": "Sales Order Detail",
            "chunk": "| ProductID | TotalUnitsSold |\n|-----------|----------------|\n| 864       | 87             |\n",
            "reference": "SELECT TOP 1 ProductID, SUM(OrderQty) AS TotalUnitsSold FROM SalesLT.SalesOrderDetail GROUP BY ProductID ORDER BY TotalUnitsSold DESC;"
        },
        {
            "title": "Product and Description",
            "chunk": "| Name           | ProductModel  |\n|----------------|---------------|\n| Classic Vest, S| Classic Vest  |\n",
            "reference": "SELECT Name, ProductModel FROM SalesLT.vProductAndDescription WHERE ProductID = 864;"
        }
    ]
}
```

The **answer** and **sources** properties can be rendered to the user to visualize the results. Markdown support is useful for complex answer outputs and explaining the source of the information.

#### Rendered Output

The top-performing product by quantity of units sold is the **Classic Vest, S** from the **Classic Vest** product model, with a total of 87 units sold [1][2].

#### Rendered Sources

| ProductID | TotalUnitsSold |
|-----------|----------------|
| 864       | 87             |

| Name           | ProductModel  |
|----------------|---------------|
| Classic Vest, S| Classic Vest  |

## Tips for good Text2SQL performance.

- Pre-assemble views to avoid the LLM having to make complex joins between multiple tables
- Give all columns and views / tables good names that are descriptive.
- Spend time providing good descriptions in the metadata for all entities and columns e.g.
    - If a column contains a value in a given currency, give the currency information in the metadata.
    - Clearly state in the **selector** what sorts of questions a given view / table can provide answers for.
- Use common codes for columns that need filtering e.g.
    - A  country can have multiple text representations e.g. United Kingdom or UK. Use ISO codes for countries, instead of text descriptions to increase the likelihood of correct and valid SQL queries.

## Production Considerations

Below are some of the considerations that should be made before using this plugin in production:

- Despite prompting to only produce **SELECT** statements, there is a danger that dangerous SQL statements could be generated.
    - Consider adding validation of the SQL query before it is executed to check it is only performing actions that you allow.
    - Consider limiting the permissions of the identity or connection string to only allow access to certain tables or perform certain query types.
- If possible, run the queries under the identity of the end user so that any row or column level security is applied to the data.
- Consider data masking for sensitive columns that you do not wish to be exposed.
