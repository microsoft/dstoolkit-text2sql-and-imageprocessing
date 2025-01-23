# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import (
    AsyncAzureOpenAI,
    OpenAIError,
    APIError,
    APIStatusError,
    BadRequestError,
    RateLimitError,
)
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from layout_holders import FigureHolder
from PIL import Image
import io
import base64


class FigureAnalysis:
    def get_image_size(self, figure: FigureHolder) -> tuple[int, int]:
        """Get the size of the image from the binary data.

        Parameters:
        - figure (FigureHolder): The figure object containing the image data.

        Returns:
        - width (int): The width of the image.
        - height (int): The height of the image."""
        # Create a BytesIO object from the binary data
        image_data = base64.b64decode(figure.data)
        image_stream = io.BytesIO(image_data)

        # Open the image using PIL
        with Image.open(image_stream) as img:
            # Get the size of the image
            width, height = img.size
            return width, height

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def understand_image_with_gptv(self, figure: FigureHolder) -> dict:
        """
        Generates a description for an image using the GPT-4V model.

        Parameters:
        - image_base64 (str): image file.
        - caption (str): The caption for the image.

        Returns:
        - img_description (str): The generated description for the image.
        """

        # Open figure and check if below minimum size
        width, height = self.get_image_size(figure)

        if width < 75 and height < 75:
            logging.info(
                "Image is too small to be analysed. Width: %i, Height: %i",
                width,
                height,
            )
            figure.description = "Irrelevant Image"

            return figure

        MAX_TOKENS = 2000
        api_version = os.environ["OpenAI__ApiVersion"]
        model_name = "gpt-4o-mini"
        deployment_id = os.environ["OpenAI__MiniCompletionDeployment"]
        azure_endpoint = os.environ["OpenAI__Endpoint"]

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )

        system_prompt = """You are an expert in technical image description and analysis for search and retrieval. Your task is to describe the key details, themes, and practical applications of the image, focusing on how the image could be used and what it helps the user achieve. Additionally, provide a brief explanation of what can be inferred from the image, such as trends, relationships, or insights.

        It is essential to include all visible labels, data points, and annotations in your description. Use natural terms and phrases that users might search for to locate the image.

        Charts and Graphs:
            - Identify the type of chart and describe the data points, trends, and labels present.
            - Explain how the chart can be used (e.g., for analyzing trends, tracking performance, or comparing metrics).
            - Describe what can be inferred, such as patterns over time, correlations, or key insights from the data.

        Maps:
            - Highlight geographical features, landmarks, and any text labels or annotations, such as street names or distances.
            - Explain how the map can be used (e.g., for navigation, travel planning, or understanding a region).
            - Describe what can be inferred, such as proximity between locations, accessibility of areas, or regional layouts.

        Diagrams:
            - Describe the components, relationships, and purpose of the diagram.
            - Explain how the diagram can be used (e.g., for understanding a process, visualizing a system, or explaining a concept).
            - Describe what can be inferred, such as how components interact, dependencies, or the overall system structure.

        Photographs or Logos:
            - Return 'Irrelevant Image' if the image is not suitable for actionable purposes like analysis or decision-making e.g. a logo, a personal photo, or a generic landscape.


        Guidelines:
            - Include all labels, text, and annotations to ensure a complete and accurate description.
            - Clearly state both the potential use of the image and what insights or information can be inferred from it.
            - Think about what the user might need from the image and describe it accordingly.
            - Make sure to consider if the image will be useful for analysis later on. If nothing valuable for analysis, decision making or information retrieval, would be able to be inferred from the image, return 'Irrelevant Image'.

        Example:
            Input:
                - A bar chart showing monthly sales for 2024, with the x-axis labeled "Month" (January to December) and the y-axis labeled "Revenue in USD." The chart shows a steady increase from January to December, with a sharp spike in November.
            Output:
                - This bar chart shows monthly sales revenue for 2024, with the x-axis labeled 'Month' (January to December) and the y-axis labeled 'Revenue in USD.' It can be used to track sales performance over the year and identify periods of high or low revenue. From the chart, it can be inferred that sales steadily increased throughout the year, with a notable spike in November, possibly due to seasonal promotions or events.

            Input:
                - A photograph of a mountain landscape with snow-capped peaks, a winding river, and a dense forest in the foreground. The image captures the natural beauty of the region and the diverse ecosystems present.
            Output:
                - Irrelevant Image"""

        user_input = "Generate a description for the image provided that can be used for search purposes."

        if figure.caption is not None and len(figure.caption) > 0:
            user_input += f""" (note: it has the following caption: {
                figure.caption})"""

        try:
            async with AsyncAzureOpenAI(
                api_key=None,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
                azure_endpoint=azure_endpoint,
                azure_deployment=deployment_id,
            ) as client:
                # We send both image caption and the image body to GPTv for better understanding
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": user_input,
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{figure.data}"
                                    },
                                },
                            ],
                        },
                    ],
                    max_tokens=MAX_TOKENS,
                )
        except (
            OpenAIError,
            APIError,
            APIStatusError,
            BadRequestError,
            RateLimitError,
        ) as e:
            logging.error(f"Failed to analyse image. Error: {e}")

            if "ResponsibleAIPolicyViolation" in e.message:
                logging.error("Responsible AI Policy Violation")
                figure.description = "Irrelevant Image"

                return figure

            raise e
        else:
            logging.info(f"Response: {response}")

            figure.description = response.choices[0].message.content

            if len(figure.description) == 0:
                logging.info("No description generated for image.")
                figure.description = "Irrelevant Image"

            logging.info(f"Image Description: {figure.description}")

            return figure

    async def analyse(self, record: dict) -> dict:
        """
        Analyse the image and generate a description for it.

        Parameters:
        - record (dict): The record containing the image and its caption.

        Returns:
        - record (dict): The record containing the image, its caption, and the generated description.
        """

        try:
            logging.info(f"Record: {record}")
            figure = FigureHolder(**record["data"]["figure"])
            updated_data = await self.understand_image_with_gptv(figure)
            logging.info(f"Updated Figure Data: {updated_data}")
        except RetryError as e:
            logging.error(f"Failed to analyse image. Error: {e}")
            logging.error(f"Failed input: {record}")
            root_cause = e.last_attempt.exception()

            if isinstance(root_cause, RateLimitError):
                return {
                    "recordId": record["recordId"],
                    "data": None,
                    "errors": [
                        {
                            "message": "Failed to analyse image due to rate limit error. Please try again later.",
                        }
                    ],
                    "warnings": None,
                }
            else:
                return {
                    "recordId": record["recordId"],
                    "data": None,
                    "errors": [
                        {
                            "message": "Failed to analyse image. Check the logs for more details.",
                        }
                    ],
                    "warnings": None,
                }
        except Exception as e:
            logging.error(f"Failed to analyse image. Error: {e}")
            logging.error(f"Failed input: {record}")
            return {
                "recordId": record["recordId"],
                "data": None,
                "errors": [
                    {
                        "message": "Failed to analyse image. Check the logs for more details.",
                    }
                ],
                "warnings": None,
            }
        else:
            return {
                "recordId": record["recordId"],
                "data": {"updated_figure": updated_data.model_dump()},
                "errors": None,
                "warnings": None,
            }
