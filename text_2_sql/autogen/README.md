# Multi-Shot Text2SQL Component - AutoGen

The implementation is written for [AutoGen](https://github.com/microsoft/autogen) in Python, although it can easily be adapted for C#.

**The provided AutoGen code only implements Iterations 5 (Agentic Approach)**

## Full Logical Flow for Agentic Vector Based Approach

The following diagram shows the logical flow within mutlti agent system. In an ideal scenario, the questions will follow the _Pre-Fetched Cache Results Path** which leads to the quickest answer generation. In cases where the question is not known, the group chat selector  will fall back to the other agents accordingly and generate the SQL query using the LLMs. The cache is then updated with the newly generated query and schemas.

Unlike the previous approaches, **gpt4o-mini** can be used as each agent's prompt is small and focuses on a single simple task.

As the query cache is shared between users (no data is stored in the cache), a new user can benefit from the pre-mapped question and schema resolution in the index.

**Database results were deliberately not stored within the cache. Storing them would have removed one of the key benefits of the Text2SQL plugin, the ability to get near-real time information inside a RAG application. Instead, the query is stored so that the most-recent results can be obtained quickly. Additionally, this retains the ability to apply Row or Column Level Security.**

![Vector Based with Query Cache Logical Flow.](../images/Agentic%20Text2SQL%20Query%20Cache.png "Agentic Vector Based with Query Cache Logical Flow")

## Provided Notebooks & Scripts
