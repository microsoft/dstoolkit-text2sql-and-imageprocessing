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

## SQL Plugin

`./plugins/sql_plugin` contains all the relevant Semantic Kernel code for the plugin.

### entities.json

To power the knowledge of the LLM, a data dictionary containing all the SQL views / table metadata is used. Whilst the LLM could query the database at runtime to find out the schemas for the database, storing them in a text file reduces the overall latency of the system and allows the metadata for each table to be adjusted in a form of prompt engineering.

### sql_plugin.py

The `./plugins/sql_plugin/sql_plugin.py` contains 3 key methods to power the Text2SQL engine.

## Tips for good Text2SQL performance.
