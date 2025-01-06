# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen_core.components.tools import FunctionToolAlias
from autogen_agentchat.agents import AssistantAgent
from text_2_sql_core.connectors.factory import ConnectorFactory
from text_2_sql_core.prompts.load import load
from autogen_text_2_sql.creators.llm_model_creator import LLMModelCreator
from jinja2 import Template


class LLMAgentCreator:
    @classmethod
    def load_agent_file(cls, name: str) -> dict:
        """Loads the agent file based on the agent name.

        Args:
        ----
            name (str): The name of the agent to load.

        Returns:
        -------
            dict: The agent file."""

        return load(name.lower())

    @classmethod
    def get_tool(cls, sql_helper, tool_name: str):
        """Gets the tool based on the tool name.
        Args:
        ----
            sql_helper (SqlConnector): The SQL helper.
            tool_name (str): The name of the tool to retrieve.

        Returns:
            FunctionToolAlias: The tool."""

        if tool_name == "sql_query_execution_tool":
            return FunctionToolAlias(
                sql_helper.query_execution_with_limit,
                description="Runs an SQL query against the SQL Database to extract information",
            )
        elif tool_name == "sql_get_entity_schemas_tool":
            return FunctionToolAlias(
                sql_helper.get_entity_schemas,
                description="Gets the schema of a view or table in the SQL Database by selecting the most relevant entity based on the search term. Extract key terms from the user question and use these as the search term. Several entities may be returned. Only use when the provided schemas in the message history are not sufficient to answer the question.",
            )
        elif tool_name == "sql_get_column_values_tool":
            return FunctionToolAlias(
                sql_helper.get_column_values,
                description="Gets the values of a column in the SQL Database by selecting the most relevant entity based on the search term. Several entities may be returned. Use this to get the correct value to apply against a filter for a user's question.",
            )
        else:
            raise ValueError(f"Tool {tool_name} not found")

    @classmethod
    def get_property_and_render_parameters(
        cls, agent_file: dict, property: str, parameters: dict
    ) -> str:
        """Gets the property from the agent file and renders the parameters.

        Args:
        ----
            agent_file (dict): The agent file.
            property (str): The property to retrieve.
            parameters (dict): The parameters to render.

        Returns:
        -------
            str: The rendered property."""
        unrendered_parameters = agent_file[property]

        rendered_template = Template(unrendered_parameters).render(parameters)

        return rendered_template

    @classmethod
    def create(cls, name: str, **kwargs) -> AssistantAgent:
        """Creates an assistant agent based on the agent name.

        Args:
        ----
            name (str): The name of the agent to create.
            **kwargs: The parameters to render.

        Returns:
        -------
            AssistantAgent: The assistant agent."""
        agent_file = cls.load_agent_file(name)

        sql_helper = ConnectorFactory.get_database_connector()

        tools = []
        if "tools" in agent_file and len(agent_file["tools"]) > 0:
            for tool in agent_file["tools"]:
                tools.append(cls.get_tool(sql_helper, tool))

        agent = AssistantAgent(
            name=name,
            tools=tools,
            model_client=LLMModelCreator.get_model(agent_file["model"]),
            description=cls.get_property_and_render_parameters(
                agent_file, "description", kwargs
            ),
            system_message=cls.get_property_and_render_parameters(
                agent_file, "system_message", kwargs
            ),
        )

        return agent
