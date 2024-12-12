# Multi-Shot Text2SQL Component - AutoGen

The implementation is written for [AutoGen](https://github.com/microsoft/autogen) in Python, although it can easily be adapted for C#.

**Still work in progress, expect a lot of updates shortly**

**The provided AutoGen code only implements Iterations 5 (Agentic Approach)**

## Full Logical Flow for Agentic Vector Based Approach

The following diagram shows the logical flow within mutlti agent system. In an ideal scenario, the questions will follow the _Pre-Fetched Cache Results Path** which leads to the quickest answer generation. In cases where the question is not known, the group chat selector  will fall back to the other agents accordingly and generate the SQL query using the LLMs. The cache is then updated with the newly generated query and schemas.

Unlike the previous approaches, **gpt4o-mini** can be used as each agent's prompt is small and focuses on a single simple task.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index. There are multiple possible strategies for updating the query cache, see the possible options in the Text2SQL README.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](../images/Agentic%20Text2SQL%20Query%20Cache.png "Agentic Vector Based with Query Cache Logical Flow")

## Provided Notebooks & Scripts

- `./Iteration 5 - Agentic Vector Based Text2SQL.ipynb` provides example of how to utilise the Agentic Vector Based Text2SQL approach to query the database. The query cache plugin will be enabled or disabled depending on the environmental parameters.

## Agents

This agentic system contains the following agents:

- **Query Cache Agent:** Responsible for checking the cache for previously asked questions.
- **Date Disambiguation Agent:** Responsible for converting relative date expressions (e.g., "16 years ago") into absolute dates. This agent ensures consistent date handling and improves query accuracy.
- **Query Decomposition Agent:** Responsible for decomposing complex questions, into sub questions that can be answered with SQL.
- **Schema Selection Agent:** Responsible for extracting key terms from the question and checking the index store for the queries.
- **SQL Query Generation Agent:** Responsible for using the previously extracted schemas and generated SQL queries to answer the question. This agent can request more schemas if needed. This agent will run the query.
- **SQL Query Verification Agent:** Responsible for verifying that the SQL query and results question will answer the question.
- **Answer Generation Agent:** Responsible for taking the database results and generating the final answer for the user.

### Date Disambiguation Agent

The Date Disambiguation Agent is a crucial addition to the pipeline that handles relative date expressions in user questions. It converts expressions like "X years ago", "last month", or "next week" into absolute dates before the question is processed by other agents.

#### Why It's Important

A question like "What country did we sell the most to in June in the year that was 16 years ago?" would break the SQL disambiguation agent without the date disambiguation agent, as it gets stuck trying to clarify what "country" means instead of first resolving the relative date to "June 2008". The date disambiguation agent ensures such questions can be processed successfully.

The agent uses LLM-based prompts rather than hardcoded patterns, making it flexible and maintainable. It processes dates before question decomposition, ensuring that all subsequent agents work with explicit, unambiguous dates.

The combination of these agents allows the system to answer complex questions, whilst staying under the token limits when including the database schemas. The query cache ensures that previously asked questions can be answered quickly to avoid degrading user experience.

All agents can be found in `/agents/`.

## agentic_text_2_sql.py

This is the main entry point for the agentic system. In here, the `Selector Group Chat` is configured with the termination conditions to orchestrate the agents within the system.

A customer transition selector is used to automatically transition between agents dependent on the last one that was used. In some cases, this choice is delegated to an LLM to decide on the most appropriate action. This mixed approach allows for speed when needed (e.g. always calling Query Cache Agent first), but will allow the system to react dynamically to the events.

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
