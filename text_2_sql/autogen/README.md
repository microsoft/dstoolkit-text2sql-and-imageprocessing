# Multi-Shot Text2SQL Component - AutoGen

The implementation is written for [AutoGen](https://github.com/microsoft/autogen) in Python, although it can easily be adapted for C#.

**Still work in progress, expect a lot of updates shortly**

**The provided AutoGen code only implements Iterations 5 (Agentic Approach)**

## Full Logical Flow for Agentic Vector Based Approach

The following diagram shows the logical flow within multi agent system. The flow begins with query rewriting to preprocess questions - this includes resolving relative dates (e.g., "last month" to "November 2024") and breaking down complex queries into simpler components. For each preprocessed question, if query cache is enabled, the system checks the cache for previously asked similar questions. In an ideal scenario, the preprocessed questions will be found in the cache, leading to the quickest answer generation. In cases where the question is not known, the group chat selector will fall back to the other agents accordingly and generate the SQL query using the LLMs. The cache is then updated with the newly generated query and schemas.

Unlike the previous approaches, **gpt4o-mini** can be used as each agent's prompt is small and focuses on a single simple task.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index. There are multiple possible strategies for updating the query cache, see the possible options in the Text2SQL README.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](../images/Agentic%20Text2SQL%20Query%20Cache.png "Agentic Vector Based with Query Cache Logical Flow")

## Provided Notebooks & Scripts

- `./Iteration 5 - Agentic Vector Based Text2SQL.ipynb` provides example of how to utilise the Agentic Vector Based Text2SQL approach to query the database. The query cache plugin will be enabled or disabled depending on the environmental parameters.

## Agents

This approach builds on the Vector Based SQL Plugin approach, but adds a agentic approach to the solution.

This agentic system contains the following agents:

- **Query Rewrite Agent:** The first agent in the flow, responsible for two key preprocessing tasks:
  1. Resolving relative dates to absolute dates (e.g., "last month" → "November 2024")
  2. Decomposing complex questions into simpler sub-questions
  This preprocessing happens before cache lookup to maximize cache effectiveness.
- **Query Cache Agent:** Responsible for checking the cache for previously asked questions. After preprocessing, each sub-question is checked against the cache if caching is enabled.
- **Schema Selection Agent:** Responsible for extracting key terms from the question and checking the index store for the queries. This agent is used when a cache miss occurs.
- **SQL Query Generation Agent:** Responsible for using the previously extracted schemas and generated SQL queries to answer the question. This agent can request more schemas if needed. This agent will run the query.
- **SQL Query Verification Agent:** Responsible for verifying that the SQL query and results question will answer the question.
- **Answer Generation Agent:** Responsible for taking the database results and generating the final answer for the user.

The combination of these agents allows the system to answer complex questions, whilst staying under the token limits when including the database schemas. The query cache ensures that previously asked questions can be answered quickly to avoid degrading user experience.

All agents can be found in `/agents/`.

## agentic_text_2_sql.py

This is the main entry point for the agentic system. In here, the system is configured with the following processing flow:

The preprocessed questions from the Query Rewrite Agent are processed sequentially through the rest of the agent pipeline. A custom transition selector automatically transitions between agents dependent on the last one that was used. The flow starts with the Query Rewrite Agent for preprocessing, followed by cache checking for each sub-question if caching is enabled. In some cases, this choice is delegated to an LLM to decide on the most appropriate action. This mixed approach allows for speed when needed (e.g. cache hits for known questions), but will allow the system to react dynamically to the events.

Note: Future development aims to implement independent processing where each preprocessed question would run in its own isolated context to prevent confusion between different parts of complex queries.

## Utils

### ai-search.py

This util file contains helper functions for interacting with AI Search.

### llm_agent_creator.py

This util file creates the agents in the AutoGen framework based on the configuration files.

### models.py

This util file creates the model connections to Azure OpenAI for the agents.

### sql.py

#### get_entity_schema()

This method is called by the AutoGen framework automatically, when instructed to do so by the LLM, to search the AI Search instance with the given text. The LLM is able to pass the key terms from the user query, and retrieve a ranked list of the most suitable entities to answer the question.

The search text passed is vectorised against the entity level **Description** columns. A hybrid Semantic Reranking search is applied against the **EntityName**, **Entity**, **Columns/Name** fields.

#### fetch_queries_from_cache()

The vector based with query cache uses the `fetch_queries_from_cache()` method to fetch the most relevant previous query and injects it into the prompt before the initial LLM call. The use of Auto-Function Calling here is avoided to reduce the response time as the cache index will always be used first.

If the score of the top result is higher than the defined threshold, the query will be executed against the target data source and the results included in the prompt. This allows us to prompt the LLM to evaluated whether it can use these results to answer the question, **without further SQL Query generation** to speed up the process.

#### run_sql_query()

This method is called by the AutoGen framework automatically, when instructed to do so by the LLM, to run a SQL query against the given database. It returns a JSON string containing a row wise dump of the results returned. These results are then interpreted to answer the question.

Additionally, if any of the cache functionality is enabled, this method will update the query cache index based on the SQL query run, and the schemas used in execution.
