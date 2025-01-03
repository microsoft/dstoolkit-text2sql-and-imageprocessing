# Multi-Shot Text2SQL Component

This portion of the repo contains code to implement a multi-shot approach to Text2SQL generation. This code can be integrated into a RAG application to allow the application to intelligently switch between different data sources (SQL, AI Search etc) to answer the question with the best possible information.

The sample provided works with Azure SQL Server, although it has been easily adapted to other SQL sources such as Snowflake.

**Three iterations on the approach are provided for SQL query generation. A prompt based approach and a two vector database based approaches. See Multi-Shot Approach for more details**

## High Level Workflow

The following diagram shows a workflow for how the Text2SQL plugin would be incorporated into a RAG application. Using the plugins available, alongside the [Function Calling](https://platform.openai.com/docs/guides/function-calling) capabilities of LLMs, the LLM can do [Chain of Thought](https://learn.microsoft.com/en-us/dotnet/ai/conceptual/chain-of-thought-prompting) reasoning to determine the steps needed to answer the question. This allows the LLM to recognise intent and therefore pick appropriate data sources based on the intent of the question.

![High level workflow for a plugin driven RAG application](../images/Plugin%20Based%20RAG%20Flow.png "High Level Workflow")

## Why Text2SQL instead of indexing the database contents?

Generating SQL queries and executing them to provide context for the RAG application provided several benefits in the use case this was designed for.

- Automatic report generation did not have to be built to automatically index the contents of the database and chunk it accordingly.
- By retaining the original table structure rather than indexing the contents, we are able to perform aggregations and calculations on the data quickly and accurately to answer numerical or statistic based questions. On a pure document based system, some of these questions are not easily answerable without pre-computing reports or extracting all the content
    - e.g. *What is our top performing sales per by quantity of units sold this month? What item did they sell the most of?* is answerable with a few simple SQL query if the correct views are exposed.
    - Without Text2SQL, a document needs to contain the top sales information for each month and be updated regularly. Additionally, we need to then store in a document all the relevant information for what they have sold that month and add into the chunk information that they are the top performing sales person.
- Pushing numerical calculations onto the source SQL engine ensures accuracy in the maths.
- Data can be updated real-time in the source database and be immediately accessible to the LLM.

## Multi-Shot Approach

A common way to perform Text2SQL generation _(Iteration 1)_ is to provide the complete schema information (either a full schema or a plain text description) inside the initial prompt. Whilst this works for small databases, there are issues with scalability as the number of tables and views exposed to the LLM increases:

- More tables / views significantly increases the number of tokens used within the prompt and the cost of inference.
- More schema information can cause confusion with the LLM. In our original use case, when exceeding 5 complex tables / views, we found that the LLM could get confused between which columns belonged to which entity and as such, would generate invalid SQL queries.
- Entity relationships between different tables is challenging for the LLM to understand.

To solve these issues, a Multi-Shot approach is developed. Below is the iterations of development on the Text2SQL query component.

![Comparison between a common Text2SQL approach and a Multi-Shot Text2SQL approach.](./images/Text2SQL%20Approaches.png "Multi Shot SQL Approaches")

Three different iterations are presented and code provided for:
 - **Iteration 2:** Injection of a brief description of the available entities is injected into the prompt. This limits the number of tokens used and avoids filling the prompt with confusing schema information.
 - **Iteration 3:** Indexing the entity definitions in a vector database, such as AI Search, and querying it to retrieve the most relevant entities for the key terms from the query.
  - **Iteration 4:** Keeping an index of commonly asked questions and which schema / SQL query they resolve to - this index is generated by the LLM when it encounters a question that has not been previously asked. Additionally, indexing the entity definitions in a vector database, such as AI Search _(same as Iteration 3)_. First querying this index to see if a similar SQL query can be obtained _(if high probability of exact SQL query match, the results can be pre-fetched)_. If not, falling back to the schema index, and querying it to retrieve the most relevant entities for the key terms from the query.
  - **Iteration 5:** Moves the Iteration 4 approach into a multi-agent approach for improved reasoning and query generation. With separation into agents, different agents can focus on one task only, and provide a better overall flow and response quality. See more details below.

All approaches limit the number of tokens used and avoids filling the prompt with confusing schema information.

Using Auto-Function calling capabilities, the LLM is able to retrieve from the plugin the full schema information for the views / tables that it considers useful for answering the question. Once retrieved, the full SQL query can then be generated. The schemas for multiple views / tables can be retrieved to allow the LLM to perform joins and other complex queries.

To improve the scalability and accuracy in SQL Query generation, the entity relationships within the database are stored within the vector store. This allows the LLM to use **entity relationship graph** to navigate complex system joins. See the details in `./data_dictionary` for more details.

For the query cache enabled approach, AI Search is used as a vector based cache, but any other cache that supports vector queries could be used, such as Redis.

### Full Logical Flow for Agentic Vector Based Approach

The following diagram shows the logical flow within mutlti agent system. In an ideal scenario, the questions will follow the _Pre-Fetched Cache Results Path** which leads to the quickest answer generation. In cases where the question is not known, the group chat selector  will fall back to the other agents accordingly and generate the SQL query using the LLMs. The cache is then updated with the newly generated query and schemas.

Unlike the previous approaches, **gpt4o-mini** can be used as each agent's prompt is small and focuses on a single simple task.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](./images/Agentic%20Text2SQL%20Query%20Cache.png "Agentic Vector Based with Query Cache Logical Flow")

### Caching Strategy

The cache strategy implementation is a simple way to prove that the system works. You can adopt several different strategies for cache population. Below are some of the strategies that could be used:

- **Pre-population:** Run an offline pipeline to generate SQL queries for the known questions that you expect from the user to prevent a 'cold start' problem.
- **Chat History Management Pipeline:** Run a real-time pipeline that logs the chat history to a database. Within this pipeline, analyse questions that are Text2SQL and generate the cache entry.
- **Positive Indication System:** Only update the cache when a user positively reacts to a question e.g. a thumbs up from the UI or doesn't ask a follow up question.
- **Always update:** Always add all questions into the cache when they are asked. The sample code in the repository currently implements this approach, but this could lead to poor SQL queries reaching the cache. One of the other caching strategies would be better production version.

### Comparison of Iterations
| | Common Text2SQL Approach | Prompt Based Multi-Shot Text2SQL Approach | Vector Based Multi-Shot Text2SQL Approach | Vector Based Multi-Shot Text2SQL Approach With Query Cache | Agentic Vector Based Multi-Shot Text2SQL Approach With Query Cache |
|-|-|-|-|-|-|
|**Advantages** | Fast for a limited number of entities. | Significant reduction in token usage. | Significant reduction in token usage. | Significant reduction in token usage.
| | | | Scales well to multiple entities. | Scales well to multiple entities. | Scales well to multiple entities with small agents. |
| | | | Uses a vector approach to detect the best fitting entity which is faster than using an LLM. Matching is offloaded to AI Search. | Uses a vector approach to detect the best fitting entity which is faster than using an LLM. Matching is offloaded to AI Search. | Uses a vector approach to detect the best fitting entity which is faster than using an LLM. Matching is offloaded to AI Search. |
| | | | | Significantly faster to answer similar questions as best fitting entity detection is skipped. Observed tests resulted in almost half the time for final output compared to the previous iteration. | Significantly faster to answer similar questions as best fitting entity detection is skipped. Observed tests resulted in almost half the time for final output compared to the previous iteration. |
| | | | | Significantly faster execution time for known questions. Total execution time can be reduced by skipping the query generation step. | Significantly faster execution time for known questions. Total execution time can be reduced by skipping the query generation step. |
| | | | |  | Instruction following and accuracy is improved by decomposing the task into smaller tasks. |
| | | | |  | Handles query decomposition for complex questions. |
|**Disadvantages** | Slows down significantly as the number of entities increases. | Uses LLM to detect the best fitting entity which is slow compared to a vector approach. | AI Search adds additional cost to the solution. | Slower than other approaches for the first time a question with no similar questions in the cache is asked. | Slower than other approaches for the first time a question with no similar questions in the cache is asked. |
| | Consumes a significant number of tokens as number of entities increases. | As number of entities increases, token usage will grow but at a lesser rate than Iteration 1. | | AI Search adds additional cost to the solution. | AI Search and multiple agents adds additional cost to the solution. |
| | LLM struggled to differentiate which table to choose with the large amount of information passed. | | | |
|**Code Availability**| | | | |
| Semantic Kernel | Yes :heavy_check_mark: | Yes :heavy_check_mark: | Yes :heavy_check_mark: | Yes :heavy_check_mark: | |
| LangChain | | | | | |
| AutoGen | | | | | Yes :heavy_check_mark: |

### Complete Execution Time Comparison for Approaches

To compare the different in complete execution time, the following questions were tested 25 times each for 4 different approaches.

Approaches:
- Prompt-based Multi-Shot (Iteration 2)
- Vector-Based Multi-Shot (Iteration 3)
- Vector-Based Multi-Shot with Query Cache (Iteration 4)
- Vector-Based Multi-shot with Pre Run Query Cache (Iteration 4)

Questions:
- What is the total revenue in June 2008?
- Give me the total number of orders in 2008?
- Which country did had the highest number of orders in June 2008?

The graph below shows the response times for the experimentation on a Known Question Set (i.e. the cache has already been populated with the query mapping by the LLM). gpt-4o was used as the completion LLM for this experiment. The response time is the complete execution time including:

- Prompt Preparation
- Question Understanding
- Cache Index Requests _(if applicable)_
- SQL Query Execution
- Interpretation and generation of answer in the correct format

![Response Time Distribution](./images/Known%20Question%20Response%20Time.png "Response Time Distribution By Approach")

The vector-based cache approaches consistently outperform those that just use a Prompt-Based or Vector-Based approach by a significant margin. Given that it is highly likely the same Text2SQL questions will be repeated often, storing the question-sql mapping leads to **significant performance increases** that are beneficial, despite the initial additional latency (between 1 - 2 seconds from testing) when a question is asked the first time.

## Sample Output

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

See `./data_dictionary` for more details on how the data dictionary is structured and ways to **automatically generate it**.

## Prompt Based SQL Plugin (Iteration 2)

This approach works well for a small number of entities (tested on up to 20 entities with hundreds of columns). It performed well on the testing, with correct metadata, we achieved 100% accuracy on the test set.

Whilst a simple and high performing approach, the downside of this approach is the increase in number of tokens as the number of entities increases. Additionally, we found that the LLM started to get "confused" on which columns belong to which entities as the number of entities increased.

## Vector Based SQL Plugin (Iterations 3 & 4)

This approach allows the system to scale without significantly increasing the number of tokens used within the system prompt. Indexing and running an AI Search instance consumes additional cost, compared to the prompt based approach.

If the query cache is enabled, we used a vector search to find the similar previously asked questions and the queries / schemas they map to. In the case of a high probability of a match, the results can be pre-run with the stored query and passed to the LLM alongside the query. If the results can answer the question, query generation can be skipped all together, speeding up the total execution time.

In the case of an unknown question, there is a minor increase in latency but the query index cache could be pre-populated before it is released to users with common questions.

The following environmental variables control the behaviour of the Vector Based Text2SQL generation:

- **Text2Sql__UseQueryCache** - controls whether the query cached index is checked before using the standard schema index.
- **Text2Sql__PreRunQueryCache** - controls whether the top result from the query cache index (if enabled) is pre-fetched against the data source to include the results in the prompt.

## Agentic Vector Based Approach (Iteration 5)

This approach builds on the the Vector Based SQL Plugin approach, but adds a agentic approach to the solution.

This agentic system contains the following agents:

- **Query Cache Agent:** Responsible for checking the cache for previously asked questions.
- **Query Decomposition Agent:** Responsible for decomposing complex questions, into sub questions that can be answered with SQL.
- **Schema Selection Agent:** Responsible for extracting key terms from the question and checking the index store for the queries.
- **SQL Query Generation Agent:** Responsible for using the previously extracted schemas and generated SQL queries to answer the question. This agent can request more schemas if needed. This agent will run the query.
- **SQL Query Verification Agent:** Responsible for verifying that the SQL query and results question will answer the question.
- **Answer Generation Agent:** Responsible for taking the database results and generating the final answer for the user.

The combination of this agent allows the system to answer complex questions, whilst staying under the token limits when including the database schemas. The query cache ensures that previously asked questions, can be answered quickly to avoid degrading user experience.

## Code Availability

| | Common Text2SQL Approach | Prompt Based Multi-Shot Text2SQL Approach | Vector Based Multi-Shot Text2SQL Approach | Vector Based Multi-Shot Text2SQL Approach With Query Cache | Agentic Vector Based Multi-Shot Text2SQL Approach With Query Cache |
|-|-|-|-|-|-|
| Semantic Kernel | Yes :heavy_check_mark: | Yes :heavy_check_mark: | Yes :heavy_check_mark: | Yes :heavy_check_mark: | |
| LangChain | | | | | |
| AutoGen | | | | | Yes :heavy_check_mark: |

See the relevant directory for the code in the provided framework.

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
