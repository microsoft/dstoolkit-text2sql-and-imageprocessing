from autogen_core.components.tools import FunctionTool
from autogen_agentchat.agents import ToolUseAssistantAgent
from utils.sql_utils import (
    query_execution,
    get_entity_schemas,
    fetch_queries_from_cache,
)
from utils.models import MINI_MODEL

SQL_QUERY_EXECUTION_TOOL = FunctionTool(
    query_execution,
    description="Runs an SQL query against the SQL Database to extract information",
)

SQL_GET_ENTITY_SCHEMAS_TOOL = FunctionTool(
    get_entity_schemas,
    description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Extract key terms from the user question and use these as the search term. Several entities may be returned. Only use when the provided schemas in the system prompt are not sufficient to answer the question.",
)

SQL_QUERY_CACHE_TOOLS = FunctionTool(
    fetch_queries_from_cache,
    description="Fetch the pre-assembled queries, and potential results from the cache based on the user's question.",
)

SQL_QUERY_AGENT = ToolUseAssistantAgent(
    name="SQL_Query_Agent",
    registered_tools=[SQL_QUERY_EXECUTION_TOOL],
    model_client=MINI_MODEL,
    description="An agent that can take a user's question and run an SQL query against the SQL Database to extract information",
    system_message="You are a helpful AI assistant. Solve tasks using your tools. Specifically, you can take into consideration the user's request and run an SQL query against the SQL Database to extract information.",
)

SQL_SCHEMA_EXTRACTION_AGENT = ToolUseAssistantAgent(
    name="SQL_Schema_Extraction_Agent",
    registered_tools=[SQL_GET_ENTITY_SCHEMAS_TOOL],
    model_client=MINI_MODEL,
    description="An agent that can take a user's question and extract the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term",
    system_message="You are a helpful AI assistant. Solve tasks using your tools. Specifically, you can take into consideration the user's request and extract the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term.",
)

SQL_QUERY_CORRECTION_AGENT = ToolUseAssistantAgent(
    name="SQL_Query_Correction_Agent",
    registered_tools=[SQL_QUERY_EXECUTION_TOOL],
    model_client=MINI_MODEL,
    description="An agent that will look at the SQL query, SQL query results and correct any mistakes in the SQL query",
    system_message="",
)

SQL_QUERY_CACHE_AGENT = ToolUseAssistantAgent(
    name="SQL_Query_Cache_Agent",
    registered_tools=[SQL_QUERY_CACHE_TOOLS],
    model_client=MINI_MODEL,
    description="An agent that will fetch the queries from the cache based on the user's question.",
    system_message="",
)
