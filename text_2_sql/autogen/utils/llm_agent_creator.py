# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import yaml
from autogen_core.components.tools import FunctionTool
from autogen_agentchat.agents import AssistantAgent
from utils.sql import (
    query_execution,
    get_entity_schemas,
)
from utils.models import MINI_MODEL
from jinja2 import Template


class LLMAgentCreator:
    @classmethod
    def load_agent_file(cls, name):
        with open(f"./agents/llm_agents/{name.lower()}.yaml", "r") as file:
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
        if tool_name == "sql_query_execution_tool":
            return FunctionTool(
                query_execution,
                description="Runs an SQL query against the SQL Database to extract information",
            )
        elif tool_name == "sql_get_entity_schemas_tool":
            return FunctionTool(
                get_entity_schemas,
                description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Extract key terms from the user question and use these as the search term. Several entities may be returned. Only use when the provided schemas in the system prompt are not sufficient to answer the question.",
            )
        else:
            raise ValueError(f"Tool {tool_name} not found")

    @classmethod
    def get_property_and_render_parameters(cls, agent_file, property, parameters):
        unrendered_parameters = agent_file[property]

        rendered_template = Template(unrendered_parameters).render(parameters)

        return rendered_template

    @classmethod
    def create(cls, name: str, **kwargs):
        agent_file = cls.load_agent_file(name)

        tools = []
        if "tools" in agent_file and len(agent_file["tools"]) > 0:
            for tool in agent_file["tools"]:
                tools.append(cls.get_tool(tool))

        agent = AssistantAgent(
            name=name,
            tools=tools,
            model_client=cls.get_model(agent_file["model"]),
            description=cls.get_property_and_render_parameters(
                agent_file, "description", kwargs
            ),
            system_message=cls.get_property_and_render_parameters(
                agent_file, "system_message", kwargs
            ),
        )

        return agent
