# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import os
import yaml
import dotenv
import json
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
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.prompt_template.prompt_template_config import PromptTemplateConfig
from utils.sql import fetch_queries_from_cache, add_queries_to_cache

logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()
kernel = Kernel()

service_id = "chat"

chat_service = AzureChatCompletion(
    service_id=service_id,
    deployment_name=os.environ["OpenAI__CompletionDeployment"],
    endpoint=os.environ["OpenAI__Endpoint"],
    api_key=os.environ["OpenAI__ApiKey"],
)
kernel.add_service(chat_service)

# Register the SQL Plugin with the Database name to use.
sql_plugin = VectorBasedSQLPlugin(database=os.environ["Text2Sql__DatabaseName"])
kernel.add_plugin(sql_plugin, "SQL")

# Load prompt and execution settings from the file
with open("./query_cache_based_prompt.yaml", "r") as file:
    data = yaml.safe_load(file.read())
    prompt_template_config = PromptTemplateConfig(**data)

chat_function = kernel.add_function(
    prompt_template_config=prompt_template_config,
    plugin_name="ChatBot",
    function_name="Chat",
)


async def ask_question(question: str, chat_history: ChatHistory) -> str:
    """Asks a question to the chatbot and returns the answer.

    Args:
        question (str): The question to ask the chatbot.
        chat_history (ChatHistory): The chat history object.

    Returns:
        str: The answer from the chatbot.
    """

    formatted_sql_cache_string = await fetch_queries_from_cache(question)

    # Create important information prompt that contains the SQL database information.
    engine_specific_rules = "Use TOP X to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error."
    important_information_prompt = f"""
    [SQL DATABASE INFORMATION]
    {sql_plugin.system_prompt(engine_specific_rules=engine_specific_rules)}
    [END SQL DATABASE INFORMATION]
    """

    question_string = f"{question}\n{formatted_sql_cache_string}"

    arguments = KernelArguments()
    arguments["chat_history"] = chat_history
    arguments["important_information"] = important_information_prompt
    arguments["user_input"] = question_string

    logging.info("Question: %s", question)

    answer = await kernel.invoke(
        function_name="Chat",
        plugin_name="ChatBot",
        arguments=arguments,
        chat_history=chat_history,
    )

    logging.info("Answer: %s", answer)

    json_answer = json.loads(str(answer))

    await add_queries_to_cache(question, json_answer)


async def measure_average_time(question: str, n=10) -> float:
    total_time = 0.0
    history = ChatHistory()

    for _ in range(n):
        start_time = time.time()
        await ask_question(question, history)
        total_time += time.time() - start_time

    # Return the average time taken
    return total_time / n


async def run_tests():
    scenarios = ["Vector", "QueryCache", "PreRunQueryCache"]

    # Define your six questions
    questions = [
        "Give me the total number of orders in 2008?",
        "What is the top performing product by quantity of units sold?",
        "Which country did we sell the most to in June 2008?",
        "How many different product categories do we have?",
    ]

    # Store average times for each question and scenario
    average_times = {scenario: [] for scenario in scenarios}

    # Run each scenario and measure times
    for scenario in scenarios:
        if scenario == "Vector":
            os.environ["Text2Sql__UseQueryCache"] = "False"
            os.environ["Text2Sql__PreRunQueryCache"] = "False"
        elif scenario == "QueryCache":
            os.environ["Text2Sql__UseQueryCache"] = "True"
            os.environ["Text2Sql__PreRunQueryCache"] = "False"
        elif scenario == "PreRunQueryCache":
            os.environ["Text2Sql__UseQueryCache"] = "True"
            os.environ["Text2Sql__PreRunQueryCache"] = "True"

        for question in questions:
            # sleep to avoid hitting gpt token limits during test
            avg_time = await measure_average_time(question)
            average_times[scenario].append(avg_time)

            await asyncio.sleep(15)

    return average_times


# Run the tests
average_times = asyncio.run(run_tests())


def plot_average_times(average_times):
    # Set width of bars
    bar_width = 0.25

    # Set position of bars on x-axis
    r1 = np.arange(4)
    r2 = [x + bar_width for x in r1]
    r3 = [x + bar_width for x in r2]

    # Make the plot
    plt.bar(
        r1,
        average_times["Vector"],
        color="b",
        width=bar_width,
        edgecolor="grey",
        label="Vector",
    )
    plt.bar(
        r2,
        average_times["QueryCache"],
        color="g",
        width=bar_width,
        edgecolor="grey",
        label="QueryCache",
    )
    plt.bar(
        r3,
        average_times["PreRunQueryCache"],
        color="r",
        width=bar_width,
        edgecolor="grey",
        label="PreRunQueryCache",
    )

    # Add labels and title
    plt.xlabel("Questions", fontweight="bold")
    plt.ylabel("Average Time (seconds)", fontweight="bold")
    plt.title("Average Response Time per Scenario")

    # Add xticks on the middle of the group bars
    plt.xticks([r + bar_width for r in range(4)], ["Q1", "Q2", "Q3", "Q4"])

    # Create legend & show graphic
    plt.legend()
    plt.savefig("average_response_time.png")
    plt.show()


# Plot the average times
plot_average_times(average_times)
