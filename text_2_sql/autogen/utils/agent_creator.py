import yaml
from autogen_core.components.tools import FunctionTool
from autogen_agentchat.agents import ToolUseAssistantAgent
from utils.sql_utils import (
    query_execution,
    get_entity_schemas,
    fetch_queries_from_cache,
)
from utils.models import MINI_MODEL


class AgentCreator:
    def load_agent_file(cls, name):
        with open(f"agents/{name.lower()}.yaml", "r") as file:
            file = yaml.safe_load(file)

        return file

    @classmethod
    def get_model(cls, model_name):
        if model_name == "gpt-4o-mini":
            return MINI_MODEL
        else:
            raise ValueError(f"Model {model_name} not found")

    @classmethod
    def get_tool(cls, tool_name):
        if tool_name == "query_execution":
            return FunctionTool(
                query_execution,
                description="Runs an SQL query against the SQL Database to extract information",
            )
        elif tool_name == "get_entity_schemas":
            return FunctionTool(
                get_entity_schemas,
                description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Extract key terms from the user question and use these as the search term. Several entities may be returned. Only use when the provided schemas in the system prompt are not sufficient to answer the question.",
            )
        elif tool_name == "fetch_queries_from_cache":
            return FunctionTool(
                fetch_queries_from_cache,
                description="Fetch the pre-assembled queries, and potential results from the cache based on the user's question.",
            )
        else:
            raise ValueError(f"Tool {tool_name} not found")

    @classmethod
    def create(cls, name: str):
        agent_file = cls.load_agent_file(name)

        tools = []
        if "tools" in agent_file and len(agent_file["tools"]):
            for tool in agent_file["tools"]:
                tools.append(cls.get_tool(tool))

        agent = ToolUseAssistantAgent(
            name=agent_file["name"],
            registered_tools=[],
            model_client=cls.get_model(agent_file["model"]),
            description=agent_file["description"],
            system_message=agent_file["system_message"],
        )

        return agent
