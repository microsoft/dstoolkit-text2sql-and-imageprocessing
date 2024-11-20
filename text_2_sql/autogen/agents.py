from autogen_agentchat.agents import ToolUseAssistantAgent
from utils.models import MINI_MODEL

ANSWER_AGENT = ToolUseAssistantAgent(
    name="Answer_Revision_Agent",
    registered_tools=[],
    model_client=MINI_MODEL,
    description="An agent that takes the user's question, the outputs from the SQL queries to provide an answer to the user's question.",
    system_message="You are a helpful AI assistant. Take the user's question and the outputs from the SQL queries to provide an answer to the user's question.",
)

QUERY_DECOMPOSITION_AGENT = ToolUseAssistantAgent(
    name="Query_Decomposition_Agent",
    registered_tools=[],
    model_client=MINI_MODEL,
    description="An agent that will decompose the user's question into smaller parts to be used in the SQL queries. Use this agent when the user's question is too complex to be answered in one SQL query.",
    system_message="You are a helpful AI assistant. Decompose the user's question into smaller parts to be used in the SQL queries. Use this agent when the user's question is too complex to be answered in one SQL query.",
)
