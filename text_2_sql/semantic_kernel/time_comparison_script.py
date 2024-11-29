# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import os
import yaml
import dotenv
import asyncio
import time
import matplotlib.pyplot as plt
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
from matplotlib.lines import Line2D

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
    engine_specific_rules = "Use TOP X at the start of the query to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error. e.g. SELECT TOP 10 * FROM table_name"
    sql_database_information_prompt = f"""
    [SQL DATABASE INFORMATION]
    {prompt_sql_plugin.sql_prompt_injection(engine_specific_rules=engine_specific_rules)}
    [END SQL DATABASE INFORMATION]
    """

    arguments = KernelArguments()
    arguments["chat_history"] = chat_history
    arguments["sql_database_information"] = sql_database_information_prompt
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
    engine_specific_rules = "Use TOP X at the start of the query to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error. e.g. SELECT TOP 10 * FROM table_name"
    sql_database_information_prompt = f"""
    [SQL DATABASE INFORMATION]
    {await vector_sql_plugin.sql_prompt_injection(
        engine_specific_rules=engine_specific_rules, question=question)}
    [END SQL DATABASE INFORMATION]
    """

    arguments = KernelArguments()

    arguments = KernelArguments()
    arguments["sql_database_information"] = sql_database_information_prompt
    arguments["user_input"] = question

    logging.info("Question: %s", question)

    answer = await vector_kernel.invoke(
        function_name="Chat",
        plugin_name="ChatBot",
        arguments=arguments,
        chat_history=chat_history,
    )

    logging.info("Answer: %s", answer)


async def measure_time(question: str, approach: str) -> float:
    history = ChatHistory()

    start_time = time.time()
    if approach == "Prompt":
        await ask_question_to_prompt_kernel(question, history)
    else:
        await ask_question_to_vector_kernel(question, history)
    time_taken = time.time() - start_time

    logging.info("Approach: %s", approach)
    logging.info("Question: %s", question)
    logging.info("Total Time: %s", time_taken)
    await asyncio.sleep(5)

    return time_taken


async def run_tests():
    approaches = ["Prompt", "Vector", "QueryCache", "PreFetchedQueryCache"]

    # Define your six questions
    questions = [
        "What is the total revenue in June 2008?",
        "Give me the total number of orders in 2008?",
        "Which country did had the highest number of orders in June 2008?",
    ]

    # Store average times for each question and approach
    timings = {}
    question_approach_sets = []

    for approach in approaches:
        timings[approach] = {i: [] for i in range(len(questions))}

    for _ in range(15):
        for q_num, question in enumerate(questions):
            for approach in approaches:
                question_approach_sets.append((q_num, question, approach))

    random.shuffle(question_approach_sets)

    for q_num, question, approach in question_approach_sets:
        if approach == "Vector" or approach == "Prompt":
            os.environ["Text2Sql__UseQueryCache"] = "False"
            os.environ["Text2Sql__PreFetchedQueryCache"] = "False"
        elif approach == "QueryCache":
            os.environ["Text2Sql__UseQueryCache"] = "True"
            os.environ["Text2Sql__PreFetchedQueryCache"] = "False"
        elif approach == "PreFetchedQueryCache":
            os.environ["Text2Sql__UseQueryCache"] = "True"
            os.environ["Text2Sql__PreFetchedQueryCache"] = "True"

        q_time = await measure_time(question, approach)
        timings[approach][q_num].append(q_time)

    return timings


# Run the tests
timings = asyncio.run(run_tests())


def plot_boxplot_times(timings):
    # Use a seaborn color palette
    colors = sns.color_palette("Set2", 4)

    # Prepare data for each question
    data = []
    num_approaches = 4  # There are 4 approaches per question

    for q_index in range(3):
        for approach_label in [
            "Prompt",
            "Vector",
            "QueryCache",
            "PreFetchedQueryCache",
        ]:
            # Append times for each approach and question
            data.append(timings[approach_label][q_index])

    # Create box plot
    plt.figure(figsize=(10, 6))

    # Create box plot with specific colors per approach
    sns.boxplot(data=data, palette=colors, showfliers=False)

    # Set x-tick labels to be the questions (Q1, Q2, Q3), placed in the center of each group
    question_ticks = [
        i + num_approaches / 2 - 0.5 for i in range(0, len(data), num_approaches)
    ]
    plt.xticks(
        ticks=question_ticks,
        labels=["Q1", "Q2", "Q3"],
        rotation=0,
        ha="center",
    )

    # Set title and axis labels
    plt.xlabel("Questions", fontweight="bold")
    plt.ylabel("Response Time (seconds)", fontweight="bold")
    plt.title("Response Time Distribution per Question, Grouped by Approach")

    legend_elements = [
        Line2D([0], [0], color=colors[0], lw=4, label="Prompt-Based"),
        Line2D([0], [0], color=colors[1], lw=4, label="Vector-Based"),
        Line2D([0], [0], color=colors[2], lw=4, label="Vector-Based with Query Cache"),
        Line2D(
            [0],
            [0],
            color=colors[3],
            lw=4,
            label="Vector-Based with Pre-Run Query Cache",
        ),
    ]

    plt.legend(handles=legend_elements, title="Approaches", loc="upper right")

    # Show the plot
    plt.savefig("images/response_time_boxplot_grouped.png")
    plt.show()


plot_boxplot_times(timings)
