# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import os
import yaml
import dotenv
import asyncio
import time
import matplotlib.pyplot as plt
import numpy as np
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
)
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.kernel import Kernel
from plugins.vector_based_sql_plugin.vector_based_sql_plugin import VectorBasedSQLPlugin
from plugins.prompt_based_sql_plugin.prompt_based_sql_plugin import PromptBasedSQLPlugin
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.prompt_template.prompt_template_config import PromptTemplateConfig
import seaborn as sns
import random

logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()

# Setup the vector kernel
vector_kernel = Kernel()

service_id = "chat"

vector_chat_service = AzureChatCompletion(
    service_id=service_id,
    deployment_name=os.environ["OpenAI__CompletionDeployment"],
    endpoint=os.environ["OpenAI__Endpoint"],
    api_key=os.environ["OpenAI__ApiKey"],
)
vector_kernel.add_service(vector_chat_service)

# Setup the prompt kernel
prompt_kernel = Kernel()

prompt_chat_service = AzureChatCompletion(
    service_id=service_id,
    deployment_name=os.environ["OpenAI__CompletionDeployment"],
    endpoint=os.environ["OpenAI__Endpoint"],
    api_key=os.environ["OpenAI__ApiKey"],
)
prompt_kernel.add_service(prompt_chat_service)

# Register the SQL Plugin with the Database name to use.
vector_sql_plugin = VectorBasedSQLPlugin()
vector_kernel.add_plugin(vector_sql_plugin, "SQL")

# Register the SQL Plugin with the Database name to use.
prompt_sql_plugin = PromptBasedSQLPlugin(database=os.environ["Text2Sql__DatabaseName"])
prompt_kernel.add_plugin(prompt_sql_plugin, "SQL")

# Load prompt and execution settings from the file
with open("./prompt.yaml", "r") as file:
    data = yaml.safe_load(file.read())
    vector_prompt_template_config = PromptTemplateConfig(**data)
    prompt_prompt_template_config = PromptTemplateConfig(**data)

chat_function = vector_kernel.add_function(
    prompt_template_config=vector_prompt_template_config,
    plugin_name="ChatBot",
    function_name="Chat",
)

chat_function = prompt_kernel.add_function(
    prompt_template_config=prompt_prompt_template_config,
    plugin_name="ChatBot",
    function_name="Chat",
)


async def ask_question_to_prompt_kernel(
    question: str, chat_history: ChatHistory
) -> str:
    """Asks a question to the chatbot and returns the answer.

    Args:
        question (str): The question to ask the chatbot.
        chat_history (ChatHistory): The chat history object.

    Returns:
        str: The answer from the chatbot.
    """

    # Create important information prompt that contains the SQL database information.
    engine_specific_rules = "Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error."
    important_information_prompt = f"""
    [SQL DATABASE INFORMATION]
    {prompt_sql_plugin.system_prompt(engine_specific_rules=engine_specific_rules)}
    [END SQL DATABASE INFORMATION]
    """

    arguments = KernelArguments()
    arguments["chat_history"] = chat_history
    arguments["important_information"] = important_information_prompt
    arguments["user_input"] = question

    logging.info("Question: %s", question)

    answer = await prompt_kernel.invoke(
        function_name="Chat",
        plugin_name="ChatBot",
        arguments=arguments,
        chat_history=chat_history,
    )

    logging.info("Answer: %s", answer)


async def ask_question_to_vector_kernel(
    question: str, chat_history: ChatHistory
) -> str:
    """Asks a question to the chatbot and returns the answer.

    Args:
        question (str): The question to ask the chatbot.
        chat_history (ChatHistory): The chat history object.

    Returns:
        str: The answer from the chatbot.
    """

    # Create important information prompt that contains the SQL database information.
    engine_specific_rules = "Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error."
    important_information_prompt = f"""
    [SQL DATABASE INFORMATION]
    {await vector_sql_plugin.system_prompt(
        engine_specific_rules=engine_specific_rules, question=question)}
    [END SQL DATABASE INFORMATION]
    """

    arguments = KernelArguments()
    arguments["chat_history"] = chat_history
    arguments["important_information"] = important_information_prompt
    arguments["user_input"] = question

    logging.info("Question: %s", question)

    answer = await vector_kernel.invoke(
        function_name="Chat",
        plugin_name="ChatBot",
        arguments=arguments,
        chat_history=chat_history,
    )

    logging.info("Answer: %s", answer)


async def measure_time(question: str, scenario: str) -> float:
    history = ChatHistory()

    start_time = time.time()
    if scenario == "Prompt":
        await ask_question_to_prompt_kernel(question, history)
    else:
        await ask_question_to_vector_kernel(question, history)
    time_taken = time.time() - start_time

    logging.info("Scenario: %s", scenario)
    logging.info("Question: %s", question)
    logging.info("Total Time: %s", time_taken)
    await asyncio.sleep(5)

    return time_taken


async def run_tests():
    scenarios = ["Prompt", "Vector", "QueryCache", "PreRunQueryCache"]

    # Define your six questions
    questions = [
        "What is the total revenue in June 2008?",
        "Give me the total number of orders in 2008?",
        "Which country did had the highest number of orders in June 2008?",
    ]

    # Store average times for each question and scenario
    average_times = {}
    question_scenario_sets = []

    for scenario in scenarios:
        average_times[scenario] = {i: [] for i in range(len(questions))}

    for _ in range(2):
        for q_num, question in enumerate(questions):
            for scenario in scenarios:
                question_scenario_sets.append((q_num, question, scenario))

    random.shuffle(question_scenario_sets)

    for q_num, question, scenario in question_scenario_sets:
        if scenario == "Vector" or scenario == "Prompt":
            os.environ["Text2Sql__UseQueryCache"] = "False"
            os.environ["Text2Sql__PreRunQueryCache"] = "False"
        elif scenario == "QueryCache":
            os.environ["Text2Sql__UseQueryCache"] = "True"
            os.environ["Text2Sql__PreRunQueryCache"] = "False"
        elif scenario == "PreRunQueryCache":
            os.environ["Text2Sql__UseQueryCache"] = "True"
            os.environ["Text2Sql__PreRunQueryCache"] = "True"

        q_time = await measure_time(question, scenario)
        logging.info("Average Time: %s", q_time)
        average_times[scenario][q_num].append(q_time)

    normalised_average_times = {}
    for scenario in scenarios:
        normalised_average_times[scenario] = []
        for q_num in range(len(questions)):
            normalised_average_times[scenario].append(
                np.median(average_times[scenario][q_num])
            )

    return normalised_average_times


# Run the tests
average_times = asyncio.run(run_tests())


def plot_average_times(average_times):
    # Set width of bars
    bar_width = 0.20

    # Use a seaborn color palette
    colors = sns.color_palette("Set2", 4)

    # Set position of bars on x-axis
    r1 = np.arange(3)
    r2 = [x + bar_width for x in r1]
    r3 = [x + bar_width for x in r2]
    r4 = [x + bar_width for x in r3]

    plt.bar(
        r1,
        average_times["Prompt"],
        color=colors[0],
        width=bar_width,
        edgecolor="grey",
        label="Prompt-Based",
    )
    plt.bar(
        r2,
        average_times["Vector"],
        color=colors[1],
        width=bar_width,
        edgecolor="grey",
        label="Vector-Based",
    )
    plt.bar(
        r3,
        average_times["QueryCache"],
        color=colors[2],
        width=bar_width,
        edgecolor="grey",
        label="Vector-Based with Query Cache",
    )
    plt.bar(
        r4,
        average_times["PreRunQueryCache"],
        color=colors[3],
        width=bar_width,
        edgecolor="grey",
        label="Vector-Based with Pre-Run Query Cache",
    )

    # Add labels and title
    plt.xlabel("Questions", fontweight="bold")
    plt.ylabel("Average Time (seconds)", fontweight="bold")
    plt.title("Average Response Time per Scenario for Known Questions")

    # Add xticks on the middle of the group bars
    plt.xticks([r + bar_width for r in range(3)], ["Q1", "Q2", "Q3"])

    # Create legend & show graphic
    plt.legend()
    plt.savefig("images/average_response_time.png")
    plt.show()


# Plot the average times
plot_average_times(average_times)
