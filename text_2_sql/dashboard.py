import io
from datetime import datetime
import gradio as gr
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
import numpy as np

# """
# REAL IMPLEMENTATION IMPORTS (currently commented out)
# import os
# import yaml
# import dotenv
# import asyncio
# import time
# from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
# from semantic_kernel.contents.chat_history import ChatHistory
# from semantic_kernel.kernel import Kernel
# from semantic_kernel.functions.kernel_arguments import KernelArguments
# from semantic_kernel.prompt_template.prompt_template_config import PromptTemplateConfig
# from plugins.vector_based_sql_plugin.vector_based_sql_plugin import VectorBasedSQLPlugin
# from plugins.prompt_based_sql_plugin.prompt_based_sql_plugin import PromptBasedSQLPlugin
# 
# # For Agentic implementation, we would need these additional imports:
# # from autogen_text_2_sql.autogen_text_2_sql import AutoGenText2Sql
# # This would give us access to the multi-agent system with:
# # - Query Cache Agent: Checks cache for previously asked questions
# # - Query Decomposition Agent: Breaks down complex questions into sub-questions
# # - Schema Selection Agent: Extracts key terms and checks index store for queries
# # - SQL Query Generation Agent: Uses schemas and previous queries to generate SQL
# # - SQL Query Verification Agent: Verifies SQL query and results
# # - Answer Generation Agent: Takes DB results and generates final answer
# """

plt.rcParams.update({
    "axes.facecolor": "#121212",
    "figure.facecolor": "#121212",
    "axes.edgecolor": "white",
    "axes.labelcolor": "white",
    "xtick.color": "white",
    "ytick.color": "white",
    "grid.color": "#333333",
    "text.color": "white"
})

approaches = ["Prompt", "Vector", "QueryCache",
              "PreFetchedQueryCache", "Agentic"]
approach_params = {
    "Prompt": (6.0, 0.5),
    "Vector": (4.0, 0.7),
    "QueryCache": (3.0, 0.5),
    "PreFetchedQueryCache": (2.0, 0.4),
    "Agentic": (1.0, 0.3)
}
NUM_ITERATIONS = 20

# """
# REAL IMPLEMENTATION SETUP (currently commented out)
# 
# def setup_kernels():
#     # Setup the vector kernel
#     vector_kernel = Kernel()
#     prompt_kernel = Kernel()
#     
#     service_id = "chat"
#     
#     # Setup vector chat service
#     vector_chat_service = AzureChatCompletion(
#         service_id=service_id,
#         deployment_name=os.environ["OpenAI__CompletionDeployment"],
#         endpoint=os.environ["OpenAI__Endpoint"],
#         api_key=os.environ["OpenAI__ApiKey"],
#     )
#     vector_kernel.add_service(vector_chat_service)
#     
#     # Setup prompt chat service
#     prompt_chat_service = AzureChatCompletion(
#         service_id=service_id,
#         deployment_name=os.environ["OpenAI__CompletionDeployment"],
#         endpoint=os.environ["OpenAI__Endpoint"],
#         api_key=os.environ["OpenAI__ApiKey"],
#     )
#     prompt_kernel.add_service(prompt_chat_service)
#     
#     # Register plugins
#     vector_sql_plugin = VectorBasedSQLPlugin()
#     vector_kernel.add_plugin(vector_sql_plugin, "SQL")
#     
#     prompt_sql_plugin = PromptBasedSQLPlugin(database=os.environ["Text2Sql__DatabaseName"])
#     prompt_kernel.add_plugin(prompt_sql_plugin, "SQL")
#     
#     # Load prompt config
#     with open("./prompt.yaml", "r") as file:
#         data = yaml.safe_load(file.read())
#         vector_prompt_template_config = PromptTemplateConfig(**data)
#         prompt_prompt_template_config = PromptTemplateConfig(**data)
#     
#     # Add chat functions
#     vector_kernel.add_function(
#         prompt_template_config=vector_prompt_template_config,
#         plugin_name="ChatBot",
#         function_name="Chat",
#     )
#     
#     prompt_kernel.add_function(
#         prompt_template_config=prompt_prompt_template_config,
#         plugin_name="ChatBot",
#         function_name="Chat",
#     )
#     
#     return vector_kernel, prompt_kernel, vector_sql_plugin, prompt_sql_plugin
#
# async def ask_question_to_prompt_kernel(question: str, kernel, plugin, chat_history: ChatHistory) -> float:
#     start_time = time.time()
#     
#     engine_specific_rules = "Use TOP X at the start of the query to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error. e.g. SELECT TOP 10 * FROM table_name"
#     sql_database_information_prompt = f"""
#     [SQL DATABASE INFORMATION]
#     {plugin.sql_prompt_injection(engine_specific_rules=engine_specific_rules)}
#     [END SQL DATABASE INFORMATION]
#     """
#     
#     arguments = KernelArguments()
#     arguments["chat_history"] = chat_history
#     arguments["sql_database_information"] = sql_database_information_prompt
#     arguments["user_input"] = question
#     
#     await kernel.invoke(
#         function_name="Chat",
#         plugin_name="ChatBot",
#         arguments=arguments,
#         chat_history=chat_history,
#     )
#     
#     return time.time() - start_time
#
# async def ask_question_to_vector_kernel(question: str, kernel, plugin, chat_history: ChatHistory) -> float:
#     start_time = time.time()
#     
#     engine_specific_rules = "Use TOP X at the start of the query to limit the number of rows returned instead of LIMIT X. NEVER USE LIMIT X as it produces a syntax error. e.g. SELECT TOP 10 * FROM table_name"
#     sql_database_information_prompt = f"""
#     [SQL DATABASE INFORMATION]
#     {await plugin.sql_prompt_injection(engine_specific_rules=engine_specific_rules, question=question)}
#     [END SQL DATABASE INFORMATION]
#     """
#     
#     arguments = KernelArguments()
#     arguments["sql_database_information"] = sql_database_information_prompt
#     arguments["user_input"] = question
#     
#     await kernel.invoke(
#         function_name="Chat",
#         plugin_name="ChatBot",
#         arguments=arguments,
#         chat_history=chat_history,
#     )
#     
#     return time.time() - start_time
#
# async def measure_real_time(question: str, approach: str, kernels_and_plugins) -> float:
#     vector_kernel, prompt_kernel, vector_sql_plugin, prompt_sql_plugin = kernels_and_plugins
#     history = ChatHistory()
#     
#     if approach == "Prompt":
#         os.environ["Text2Sql__UseQueryCache"] = "False"
#         os.environ["Text2Sql__PreFetchedQueryCache"] = "False"
#         return await ask_question_to_prompt_kernel(question, prompt_kernel, prompt_sql_plugin, history)
#     elif approach == "Vector":
#         os.environ["Text2Sql__UseQueryCache"] = "False"
#         os.environ["Text2Sql__PreFetchedQueryCache"] = "False"
#         return await ask_question_to_vector_kernel(question, vector_kernel, vector_sql_plugin, history)
#     elif approach == "QueryCache":
#         os.environ["Text2Sql__UseQueryCache"] = "True"
#         os.environ["Text2Sql__PreFetchedQueryCache"] = "False"
#         return await ask_question_to_vector_kernel(question, vector_kernel, vector_sql_plugin, history)
#     elif approach == "PreFetchedQueryCache":
#         os.environ["Text2Sql__UseQueryCache"] = "True"
#         os.environ["Text2Sql__PreFetchedQueryCache"] = "True"
#         return await ask_question_to_vector_kernel(question, vector_kernel, vector_sql_plugin, history)
#     elif approach == "Agentic":
#         # Agentic implementation would:
#         # 1. Initialize AutoGenText2Sql with TSQL engine and rules
#         # 2. Create a group chat with specialized agents:
#         #    - Query Cache Agent: First checks if question was asked before
#         #    - Query Decomposition Agent: Breaks complex questions into sub-questions
#         #    - Schema Selection Agent: Finds relevant schemas using vector search
#         #    - SQL Query Generation Agent: Creates SQL using schemas & previous queries
#         #    - SQL Query Verification Agent: Validates query answers the question
#         #    - Answer Generation Agent: Creates natural language response
#         # 3. Use a custom transition selector to orchestrate agent interactions
#         # 4. Leverage shared query cache between users for faster responses
#         # 5. Support complex questions through decomposition while staying under token limits
#         # Example implementation:
#         # agentic_text_2_sql = AutoGenText2Sql(
#         #     target_engine="TSQL",
#         #     engine_specific_rules="Use TOP X instead of LIMIT X"
#         # ).agentic_flow
#         # start_time = time.time()
#         # await agentic_text_2_sql.run_stream(task=question)
#         # return time.time() - start_time
#         return 1.0
#     
#     await asyncio.sleep(5)  # Rate limiting
#     return 0.0
# """

def simulate_one_run(question):
    results = []
    for approach in approaches:
        mean, std = approach_params[approach]
        rt = np.clip(np.random.normal(mean, std), 0.1, None)
        results.append({
            "Approach": approach,
            "Response Time (seconds)": rt,
            "Timestamp": datetime.now().strftime("%H:%M:%S"),
            "Question": question
        })
    return pd.DataFrame(results)

def create_box_plot(df):
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#121212')
    sns.boxplot(
        x="Approach",
        y="Response Time (seconds)",
        data=df,
        showfliers=False,
        linewidth=1.2,
        width=0.6,
        boxprops=dict(facecolor="#1f4f7b", edgecolor="white"),
        medianprops=dict(color="white"),
        whiskerprops=dict(color="white"),
        capprops=dict(color="white"),
        ax=ax
    )
    sns.stripplot(
        x="Approach",
        y="Response Time (seconds)",
        data=df,
        color="#80BFEA",
        size=3,
        alpha=0.8,
        ax=ax
    )

    ax.set_title("Response Time Distribution by Approach",
                 fontsize=14, color='white')
    ax.set_xlabel("Approach", fontsize=12, color='white')
    ax.set_ylabel("Response Time (seconds)", fontsize=12, color='white')
    ax.yaxis.grid(True, color="#333333")
    ax.xaxis.grid(False)

    for spine in ax.spines.values():
        spine.set_color('white')

    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, facecolor="#121212")
    buf.seek(0)
    plt.close(fig)
    return Image.open(buf)

def run_test(question):
    df = pd.DataFrame()
    yield "Running tests...", None
    for i in range(1, NUM_ITERATIONS + 1):
        new_data = simulate_one_run(question)
        df = pd.concat([df, new_data], ignore_index=True)
        image = create_box_plot(df)
        msg = f"Collecting data... Iteration {i}/{NUM_ITERATIONS}"
        yield msg, image

    yield "Analysis complete!", image

# """
# REAL IMPLEMENTATION RUN TEST (currently commented out)
# async def run_real_test(question):
#     dotenv.load_dotenv()
#     kernels_and_plugins = setup_kernels()
#     
#     df = pd.DataFrame()
#     yield "Running tests...", None
#     
#     for i in range(1, NUM_ITERATIONS + 1):
#         results = []
#         for approach in approaches:
#             rt = await measure_real_time(question, approach, kernels_and_plugins)
#             results.append({
#                 "Approach": approach,
#                 "Response Time (seconds)": rt,
#                 "Timestamp": datetime.now().strftime("%H:%M:%S"),
#                 "Question": question
#             })
#         
#         new_data = pd.DataFrame(results)
#         df = pd.concat([df, new_data], ignore_index=True)
#         image = create_box_plot(df)
#         msg = f"Collecting data... Iteration {i}/{NUM_ITERATIONS}"
#         yield msg, image
#     
#     yield "Analysis complete!", image
# """

custom_css = """
body {
    background-color: #202020;
    color: white;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
}

.gradio-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 1rem;
}

#input-row .gr-textbox {
    width: 100%;
    margin-bottom: 0.5rem;
}

#run-button {
    background-color: #0078D4 !important;
    border: none !important;
    border-radius: 4px !important;
    color: white !important;
    font-size: 14px !important;
    padding: 8px 16px !important;
    height: auto !important;
    transition: background-color 0.2s !important;
}

#run-button:hover {
    background-color: #005A9E !important;
}

.gr-form {
    background: transparent !important;
    border: none !important;
}

.gr-box {
    border-radius: 8px !important;
    background: #2d2d2d !important;
    border: 1px solid #404040 !important;
}

.gr-padded {
    padding: 1rem !important;
}

.gr-input, .gr-select {
    background: #333 !important;
    border: 1px solid #404040 !important;
    color: white !important;
}

.gr-input:focus {
    border-color: #0078D4 !important;
}

.gr-button-primary {
    background: #0078D4 !important;
}

.gr-button-secondary {
    background: #333 !important;
    color: white !important;
}

/* Remove orange loading colors */
.progress-bar, 
.progress-bar-fill, 
progress[value] {
    background-color: #0078D4 !important;
    color: #0078D4 !important;
    border-color: #0078D4 !important;
}

.loading {
    color: #0078D4 !important;
    border-color: #0078D4 !important;
}

.progress {
    background-color: #0078D4 !important;
}

.meta-text-center {
    color: #0078D4 !important;
}

.pending {
    background-color: #2d2d2d !important;
}

.generating {
    background-color: #2d2d2d !important;
}

.progress-text {
    color: white !important;
}

.gr-image {
    background-color: #2d2d2d !important;
}

.gr-image-awaiting {
    background-color: #2d2d2d !important;
}

/* Loading spinner */
.loader {
    border-top-color: #0078D4 !important;
    border-right-color: #0078D4 !important;
    border-bottom-color: #0078D4 !important;
    border-left-color: transparent !important;
}

/* Queue progress bar */
.queue-position {
    background-color: #0078D4 !important;
}

.progress-bar-background {
    background-color: #2d2d2d !important;
}
"""

with gr.Blocks(css=custom_css, title="Text-to-SQL Demo") as demo:
    gr.Markdown("# Text-to-SQL Performance Analysis", elem_id="title")
    gr.Markdown(
        "Compare response times across different Text-to-SQL approaches", elem_id="subtitle")

    with gr.Row():
        with gr.Column(scale=2):
            result_image = gr.Image(
                type="pil", label="Performance Distribution")
        with gr.Column(scale=1):
            user_input = gr.Textbox(
                label="Sample Question",
                value="What is the total revenue in June 2008?",
                lines=2
            )
            run_button = gr.Button(
                "Analyze Performance",
                elem_id="run-button"
            )
            status_text = gr.Markdown(
                "Enter a question and click Analyze Performance to begin.")

    run_button.click(
        fn=run_test,  # To use real implementation, change to run_real_test
        inputs=user_input,
        outputs=[status_text, result_image],
        queue=True
    )

if __name__ == "__main__":
    demo.launch(
        share=False,
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False
    )
