# Multi-Shot Text2SQL Component

This portion of the repo contains code to implement a multi-shot approach to Text2SQL generation. This code can be integrated into a RAG application to allow the application to intelligently switch between different data sources (SQL, AI Search etc) to answer the question with the best possible information.

The sample provided works with Azure SQL Server, although it has been easily adapted to other SQL sources such as Snowflake.

> [!NOTE]
>
> See `GETTING_STARTED.md` for a step by step guide of how to use the accelerator.

## Why Text2SQL instead of indexing the database contents?

Generating SQL queries and executing them to provide context for the RAG application provided several benefits in the use case this was designed for.

- Automatic report generation did not have to be built to automatically index the contents of the database and chunk it accordingly.
- By retaining the original table structure rather than indexing the contents, we are able to perform aggregations and calculations on the data quickly and accurately to answer numerical or statistic based questions. On a pure document based system, some of these questions are not easily answerable without pre-computing reports or extracting all the content
    - e.g. *What is our top performing sales per by quantity of units sold this month? What item did they sell the most of?* is answerable with a few simple SQL query if the correct views are exposed.
    - Without Text2SQL, a document needs to contain the top sales information for each month and be updated regularly. Additionally, we need to then store in a document all the relevant information for what they have sold that month and add into the chunk information that they are the top performing sales person.
- Pushing numerical calculations onto the source SQL engine ensures accuracy in the maths.
- Data can be updated real-time in the source database and be immediately accessible to the LLM.

## High Level Workflow - Multi-Shot Approach

A common way to perform Text2SQL generation _(Iteration 1)_ is to provide the complete schema information (either a full schema or a plain text description) inside the initial prompt. Whilst this works for small databases, there are issues with scalability as the number of tables and views exposed to the LLM increases:

- More tables / views significantly increases the number of tokens used within the prompt and the cost of inference.
- More schema information can cause confusion with the LLM. In our original use case, when exceeding 5 complex tables / views, we found that the LLM could get confused between which columns belonged to which entity and as such, would generate invalid SQL queries.
- Entity relationships between different tables is challenging for the LLM to understand.

To solve these issues, a Multi-Shot approach is developed. Below is the iterations of development on the Text2SQL query component.

![Comparison between a common Text2SQL approach and a Multi-Shot Text2SQL approach.](./images/Text2SQL%20Approaches.png "Multi Shot SQL Approaches")

> [!NOTE]
>
> - Previous versions of this approach have now been moved to `previous_iterations/semantic_kernel`. These will not be updated or maintained.

Our approach has evolved as the system has matured into an multi-agent approach that brings improved reasoning, speed and instruction following capabilities. With separation into agents, different agents can focus on one task only, and provide a better overall flow and response quality.

Using Auto-Function calling capabilities, the LLM is able to retrieve from the plugin the full schema information for the views / tables that it considers useful for answering the question. Once retrieved, the full SQL query can then be generated. The schemas for multiple views / tables can be retrieved to allow the LLM to perform joins and other complex queries.

To improve the scalability and accuracy in SQL Query generation, the entity relationships within the database are stored within the vector store. This allows the LLM to use **entity relationship graph** to navigate complex system joins. See the details in `./data_dictionary` for more details.

For the query cache enabled approach, AI Search is used as a vector based cache, but any other cache that supports vector queries could be used, such as Redis.

### Full Logical Flow for Agentic Vector Based Approach

The following diagram shows the logical flow within mutlti agent system. In an ideal scenario, the questions will follow the _Pre-Fetched Cache Results Path** which leads to the quickest answer generation. In cases where the question is not known, the group chat selector  will fall back to the other agents accordingly and generate the SQL query using the LLMs. The cache is then updated with the newly generated query and schemas.

Unlike the previous approaches, **gpt4o-mini** can be used as each agent's prompt is small and focuses on a single simple task.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](./images/Agentic%20Text2SQL%20Query%20Cache.png "Agentic Vector Based with Query Cache Logical Flow")

## Agents

This agentic system contains the following agents:

- **Query Cache Agent:** Responsible for checking the cache for previously asked questions.
- **Query Decomposition Agent:** Responsible for decomposing complex questions, into sub questions that can be answered with SQL.
- **Schema Selection Agent:** Responsible for extracting key terms from the question and checking the index store for the queries.
- **SQL Query Generation Agent:** Responsible for using the previously extracted schemas and generated SQL queries to answer the question. This agent can request more schemas if needed. This agent will run the query.
- **SQL Query Verification Agent:** Responsible for verifying that the SQL query and results question will answer the question.
- **Answer Generation Agent:** Responsible for taking the database results and generating the final answer for the user.

The combination of this agent allows the system to answer complex questions, whilst staying under the token limits when including the database schemas. The query cache ensures that previously asked questions, can be answered quickly to avoid degrading user experience.

### Parallel execution

After the first agent has rewritten and decomposed the user input, we execute each of the individual questions in parallel for the quickest time to generate an answer.

### Caching Strategy

The cache strategy implementation is a simple way to prove that the system works. You can adopt several different strategies for cache population. Below are some of the strategies that could be used:

- **Pre-population:** Run an offline pipeline to generate SQL queries for the known questions that you expect from the user to prevent a 'cold start' problem.
- **Chat History Management Pipeline:** Run a real-time pipeline that logs the chat history to a database. Within this pipeline, analyse questions that are Text2SQL and generate the cache entry.
- **Positive Indication System:** Only update the cache when a user positively reacts to a question e.g. a thumbs up from the UI or doesn't ask a follow up question.
- **Always update:** Always add all questions into the cache when they are asked. The sample code in the repository currently implements this approach, but this could lead to poor SQL queries reaching the cache. One of the other caching strategies would be better production version.

## Sample Output

> [!NOTE]
>
> - Full payloads for input / outputs can be found in `text_2_sql_core/src/text_2_sql_core/payloads/interaction_payloads.py`.

### What is the top performing product by quantity of units sold?

#### SQL Query Generated

*SELECT TOP 1 ProductID, SUM(OrderQty) AS TotalUnitsSold FROM SalesLT.SalesOrderDetail GROUP BY ProductID ORDER BY TotalUnitsSold DESC*

#### JSON Result

```json
{
    "answer": "The top-performing product by quantity of units sold is the **Classic Vest, S** from the **Classic Vest** product model, with a total of 87 units sold [1][2].",
    "sources": [
        {
            "sql_rows": "| ProductID | TotalUnitsSold |\n|-----------|----------------|\n| 864       | 87             |\n",
            "sql_query": "SELECT TOP 1 ProductID, SUM(OrderQty) AS TotalUnitsSold FROM SalesLT.SalesOrderDetail GROUP BY ProductID ORDER BY TotalUnitsSold DESC;"
        },
        {
            "sql_rows": "| Name           | ProductModel  |\n|----------------|---------------|\n| Classic Vest, S| Classic Vest  |\n",
            "sql_query": "SELECT Name, ProductModel FROM SalesLT.vProductAndDescription WHERE ProductID = 864;"
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

## Disambiguation Requests

If the LLM is unable to understand or answer the question asked, it can ask the user follow up questions with a DisambiguationRequest. In cases where multiple columns may be the correct one, or that there user may be referring to several different filter values, the LLM can produce a series of options for the end user to select from.

## Data Dictionary

### entities.json

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

> [!NOTE]
>
> - See `./data_dictionary` for more details on how the data dictionary is structured and ways to **automatically generate it**.

## Tips for good Text2SQL performance.

- Pre-assemble views to avoid the LLM having to make complex joins between multiple tables
- Give all columns and views / tables good names that are descriptive.
- Spend time providing good descriptions in the metadata for all entities and columns e.g.
    - If a column contains a value in a given currency, give the currency information in the metadata.
    - Clearly state in the **description** what sorts of questions a given view / table can provide answers for.
- Use common codes for columns that need filtering e.g.
    - A  country can have multiple text representations e.g. United Kingdom or UK. Use ISO codes for countries, instead of text descriptions to increase the likelihood of correct and valid SQL queries.

## Production Considerations

Below are some of the considerations that should be made before using this plugin in production:

- Despite prompting to only produce **SELECT** statements, there is a danger that dangerous SQL statements could be generated.
    - Consider adding validation of the SQL query before it is executed to check it is only performing actions that you allow.
    - Consider limiting the permissions of the identity or connection string to only allow access to certain tables or perform certain query types.
- If possible, run the queries under the identity of the end user so that any row or column level security is applied to the data.
- Consider data masking for sensitive columns that you do not wish to be exposed.
- The vector matching for the index could be run locally, rather than in an external service such as Azure AI Search. For speed of implementation, AI Search was used in this proof of concept.
