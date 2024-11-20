from autogen_core.components.tools import FunctionTool
from autogen_agentchat.agents import ToolUseAssistantAgent
from utils.sql_utils import (
    query_execution,
    get_entity_schemas,
    fetch_queries_from_cache,
)
from utils.models import MINI_MODEL
from utils.prompts import load_system_message, load_description

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

SQL_QUERY_GENERATION_AGENT = ToolUseAssistantAgent(
    name="SQL_Query_Generation_Agent",
    registered_tools=[SQL_QUERY_EXECUTION_TOOL],
    model_client=MINI_MODEL,
    description=load_description("sql_query_generation_agent"),
    system_message=load_system_message("sql_query_generation_agent"),
)

SQL_SCHEMA_SELECTION_AGENT = ToolUseAssistantAgent(
    name="SQL_Schema_Selection_Agent",
    registered_tools=[SQL_GET_ENTITY_SCHEMAS_TOOL],
    model_client=MINI_MODEL,
    description=load_description("sql_schema_selection_agent"),
    system_message=load_system_message("sql_schema_selection_agent"),
)

SQL_QUERY_CORRECTION_AGENT = ToolUseAssistantAgent(
    name="SQL_Query_Correction_Agent",
    registered_tools=[SQL_QUERY_EXECUTION_TOOL, SQL_GET_ENTITY_SCHEMAS_TOOL],
    model_client=MINI_MODEL,
    description=load_description("sql_query_correction_agent"),
    system_message=load_system_message("sql_query_correction_agent"),
)

SQL_QUERY_CACHE_AGENT = ToolUseAssistantAgent(
    name="SQL_Query_Cache_Agent",
    registered_tools=[SQL_QUERY_CACHE_TOOLS],
    model_client=MINI_MODEL,
    description=load_description("sql_query_cache_agent"),
    system_message=load_system_message("sql_query_cache_agent"),
)
