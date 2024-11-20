from autogen_agentchat.agents import ToolUseAssistantAgent
from utils.models import MINI_MODEL
from utils.prompts import load_system_message, load_description

ANSWER_AGENT = ToolUseAssistantAgent(
    name="Answer_Agent",
    registered_tools=[],
    model_client=MINI_MODEL,
    description=load_description("answer_agent"),
    system_message=load_system_message("answer_agent"),
)

QUESTION_DECOMPOSITION_AGENT = ToolUseAssistantAgent(
    name="Question_Decomposition_Agent",
    registered_tools=[],
    model_client=MINI_MODEL,
    description=load_description("question_decomposition_agent"),
    system_message=load_system_message("question_decomposition_agent"),
)
