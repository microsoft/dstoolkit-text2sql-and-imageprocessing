# Multi-Shot Text2SQL Component - Semantic Kernel

The implementation is written for [Semantic Kernel](https://github.com/microsoft/semantic-kernel) in Python, although it can easily be adapted for C#.

**The provided Semantic Kernel code implements Iterations 2, 3 & 4.**

## Full Logical Flow for Vector Based Approach

The following diagram shows the logical flow within the Vector Based plugin. In an ideal scenario, the questions will follow the _Pre-Fetched Cache Results Path** which leads to the quickest answer generation. In cases where the question is not known, the plugin will fall back the other paths accordingly and generate the SQL query using the LLMs.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index. There are multiple possible strategies for updating the query cache, see the possible options in the Text2SQL README.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](../images/Text2SQL%20Query%20Cache.png "Vector Based with Query Cache Logical Flow")

## Provided Notebooks & Scripts

- `./Iteration 2 - Prompt Based Text2SQL.ipynb` provides example of how to utilise the Prompt Based Text2SQL plugin to query the database.
- `./Iterations 3 & 4 - Vector Based Text2SQL.ipynb` provides example of how to utilise the Vector Based Text2SQL plugin to query the database. The query cache plugin will be enabled or disabled depending on the environmental parameters.
- `./time_comparison_script.py` provides a utility script for performing time based comparisons between the different approaches.

### ai-search.py

This util file contains helper functions for interacting with AI Search.

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
