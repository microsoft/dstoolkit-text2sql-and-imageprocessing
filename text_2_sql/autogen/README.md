# Multi-Shot Text2SQL Component - AutoGen

The implementation is written for [AutoGen](https://github.com/microsoft/autogen) in Python, although it can easily be adapted for C#.

**Still work in progress, expect a lot of updates shortly**

**The provided AutoGen code only implements Iterations 5 (Agentic Approach)**

## Full Logical Flow for Agentic Vector Based Approach

The following diagram shows the logical flow within the multi-agent system. The flow begins with query rewriting to preprocess questions - this includes resolving relative dates (e.g., "last month" to "November 2024") and breaking down complex queries into simpler components. For each preprocessed question, if query cache is enabled, the system checks the cache for previously asked similar questions. In an ideal scenario, the preprocessed questions will be found in the cache, leading to the quickest answer generation. In cases where the question is not known, the system will fall back to the other agents accordingly and generate the SQL query using the LLMs. The cache is then updated with the newly generated query and schemas.

Unlike the previous approaches, **gpt4o-mini** can be used as each agent's prompt is small and focuses on a single simple task.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index. There are multiple possible strategies for updating the query cache, see the possible options in the Text2SQL README.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](../images/Agentic%20Text2SQL%20Query%20Cache.png "Agentic Vector Based with Query Cache Logical Flow")

## Agent Flow in Detail

The agent flow is managed by a sophisticated selector system in `autogen_text_2_sql.py`. Here's how it works:

1. **Initial Entry**
   - Every question starts with the Query Rewrite Agent
   - This agent processes dates and breaks down complex questions

2. **Post Query Rewrite**
   - If query cache is enabled (`Text2Sql__UseQueryCache=True`):
     - Flow moves to SQL Query Cache Agent
   - If cache is disabled:
     - Flow moves directly to Schema Selection Agent

3. **Cache Check Branch**
   - If cache hit found:
     - With pre-run results: Goes to SQL Query Correction Agent
     - Without pre-run results: Goes to SQL Query Generation Agent
   - If cache miss:
     - Goes to Schema Selection Agent

4. **Schema Selection Branch**
   - Schema Selection Agent finds relevant schemas
   - Always moves to SQL Disambiguation Agent
   - Disambiguation Agent clarifies any schema ambiguities
   - Then moves to SQL Query Generation Agent

5. **Query Generation and Correction Loop**
   - SQL Query Generation Agent creates the query
   - SQL Query Correction Agent verifies/corrects the query
   - Based on correction results:
     - If query needs execution: Returns to Correction Agent
     - If query needs fixes: Returns to Generation Agent
     - If answer and sources ready: Completes flow
     - If error occurs: Returns to Generation Agent

The flow uses termination conditions:
- Explicit "TERMINATE" mention
- Presence of both "answer" and "sources"
- Maximum of 20 messages reached

## Provided Notebooks & Scripts

- `./Iteration 5 - Agentic Vector Based Text2SQL.ipynb` provides example of how to utilize the Agentic Vector Based Text2SQL approach to query the database. The query cache plugin will be enabled or disabled depending on the environmental parameters.

## Agents

This approach builds on the Vector Based SQL Plugin approach, but adds an agentic approach to the solution.

The agentic system contains the following agents:

- **Query Rewrite Agent:** The first agent in the flow, responsible for two key preprocessing tasks:
  1. Resolving relative dates to absolute dates (e.g., "last month" → "November 2024")
  2. Decomposing complex questions into simpler sub-questions
  This preprocessing happens before cache lookup to maximize cache effectiveness.

- **Query Cache Agent:** (Optional) Responsible for checking the cache for previously asked questions. After preprocessing, each sub-question is checked against the cache if caching is enabled.

- **Schema Selection Agent:** Responsible for extracting key terms from the question and checking the index store for relevant database schemas. This agent is used when a cache miss occurs.

- **SQL Disambiguation Agent:** Responsible for clarifying any ambiguities in the schema selection and ensuring the correct tables and columns are selected for the query.

- **SQL Query Generation Agent:** Responsible for using the previously extracted schemas to generate SQL queries that answer the question. This agent can request more schemas if needed.

- **SQL Query Correction Agent:** Responsible for verifying and correcting the generated SQL queries, ensuring they are syntactically correct and will produce the expected results. This agent also handles the execution of queries and formatting of results.

The combination of these agents allows the system to answer complex questions while staying under token limits when including database schemas. The query cache ensures that previously asked questions can be answered quickly to avoid degrading user experience.

## Project Structure

### autogen_text_2_sql.py

This is the main entry point for the agentic system. It configures the system with a sophisticated processing flow managed by a unified selector that handles agent transitions. The flow includes:

1. Initial query rewriting for preprocessing
2. Cache checking if enabled
3. Schema selection and disambiguation
4. Query generation and correction
5. Result verification and formatting

The system uses a custom transition selector that automatically moves between agents based on the previous agent's output and the current state. This allows for dynamic reactions to different scenarios, such as cache hits, schema ambiguities, or query corrections.

### creators/

- **llm_agent_creator.py:** Creates the agents in the AutoGen framework based on configuration files
- **llm_model_creator.py:** Handles model connections and configurations for the agents

### custom_agents/

Contains specialized agent implementations:
- **sql_query_cache_agent.py:** Implements the caching functionality
- **sql_schema_selection_agent.py:** Handles schema selection and management

## Configuration

The system behavior can be controlled through environment variables:

- `Text2Sql__UseQueryCache`: Enables/disables the query cache functionality
- `Text2Sql__PreRunQueryCache`: Controls whether to pre-run cached queries
- `Text2Sql__UseColumnValueStore`: Enables/disables the column value store
- `Text2Sql__DatabaseEngine`: Specifies the target database engine

Each agent can be configured with specific parameters and prompts to optimize its behavior for different scenarios.
