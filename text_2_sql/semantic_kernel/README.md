# Multi-Shot Text2SQL Component - Semantic Kernel

The implementation is written for [Semantic Kernel](https://github.com/microsoft/semantic-kernel) in Python, although it can easily be adapted for C#.

## Provided Notebooks & Scripts

- `./rag_with_prompt_based_text_2_sql.ipynb` provides example of how to utilise the Prompt Based Text2SQL plugin to query the database.
- `./rag_with_vector_based_text_2_sql.ipynb` provides example of how to utilise the Vector Based Text2SQL plugin to query the database. The query cache plugin will be enabled or disabled depending on the environmental parameters.
- `./rag_with_ai_search_and_text_2_sql.ipynb` provides an example of how to use the Text2SQL and an AISearch plugin in parallel to automatically retrieve data from the most relevant source to answer the query.
    - This setup is useful for a production application as the SQL Database is unlikely to be able to answer all the questions a user may ask.
- `./time_comparison_script.py` provides a utility script for performing time based comparisons between the different approaches.

## Plugins

### prompt_based_sql_plugin.py

The `./plugins/prompt_based_sql_plugin/prompt_based_sql_plugin.py` contains 3 key methods to power the Prompt Based Text2SQL engine.

#### system_prompt()

This method takes the loaded `entities.json` file and generates a system prompt based on it. Here, the **EntityName** and **Description** are used to build a list of available entities for the LLM to select.

This is then inserted into a pre-made Text2SQL generation prompt that already contains optimised and working instructions for the LLM. This system prompt for the plugin is added to the main prompt file at runtime.

The **target_engine** is passed to the prompt, along with **engine_specific_rules** to ensure that the SQL queries generated work on the target engine.

#### get_entity_schema()

This method is called by the Semantic Kernel framework automatically, when instructed to do so by the LLM, to fetch the full schema definitions for a given entity. This returns a JSON string of the chosen entity which allows the LLM to understand the column definitions and their associated metadata. This can be called in parallel for multiple entities.

#### run_sql_query()

This method is called by the Semantic Kernel framework automatically, when instructed to do so by the LLM, to run a SQL query against the given database. It returns a JSON string containing a row wise dump of the results returned. These results are then interpreted to answer the question.

### vector_based_sql_plugin.py

The `./plugins/vector_based_sql_plugin/vector_based_sql_plugin.py` contains 3 key methods to power the Vector Based Text2SQL engine.


#### system_prompt()

This method simply returns a pre-made system prompt that contains optimised and working instructions for the LLM. This system prompt for the plugin is added to the main prompt file at runtime.

The **target_engine** is passed to the prompt, along with **engine_specific_rules** to ensure that the SQL queries generated work on the target engine.

**If the query cache is enabled, the prompt is adjusted to instruct the LLM to look at the cached data and results first, before calling `get_entity_schema()`.**

#### get_entity_schema()

This method is called by the Semantic Kernel framework automatically, when instructed to do so by the LLM, to search the AI Search instance with the given text. The LLM is able to pass the key terms from the user query, and retrieve a ranked list of the most suitable entities to answer the question.

The search text passed is vectorised against the entity level **Description** columns. A hybrid Semantic Reranking search is applied against the **EntityName**, **Entity**, **Columns/Name** fields.

#### fetch_queries_from_cache()

The vector based with query cache uses the `fetch_queries_from_cache()` method to fetch the most relevant previous query and injects it into the prompt before the initial LLM call. The use of Auto-Function Calling here is avoided to reduce the response time as the cache index will always be used first.

If the score of the top result is higher than the defined threshold, the query will be executed against the target data source and the results included in the prompt. This allows us to prompt the LLM to evaluated whether it can use these results to answer the question, **without further SQL Query generation** to speed up the process.

#### run_sql_query()

This method is called by the Semantic Kernel framework automatically, when instructed to do so by the LLM, to run a SQL query against the given database. It returns a JSON string containing a row wise dump of the results returned. These results are then interpreted to answer the question.

Additionally, if any of the cache functionality is enabled, this method will update the query cache index based on the SQL query run, and the schemas used in execution.
