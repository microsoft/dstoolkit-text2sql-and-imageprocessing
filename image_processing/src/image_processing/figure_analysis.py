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
)
from tenacity import retry, stop_after_attempt, wait_exponential
from layout_holders import FigureHolder


class FigureAnalysis:
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

        MAX_TOKENS = 2000
        api_version = os.environ["OpenAI__ApiVersion"]
        model = os.environ["OpenAI__CompletionDeployment"]

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )

        system_prompt = """You are an expert in technical image analysis. Your task is to provided analysis of images. You should FOCUS on what info can be inferred from the image and the meaning of the data inside the image. Draw actionable insights and conclusions from the image. Do not describe the image in a general way or describe the image in a way that is not useful for decision-making.

        If the image is a chart for instance, you should describe the data trends, patterns, and insights that can be drawn from the chart. For example, you could describe the increase or decrease in sales over time, the peak sales period, or the sales performance of a particular product.

        If the image is a map, you should describe the geographical features, landmarks, and any other relevant information that can be inferred from the map.

        If the image is a diagram, you should describe the components, relationships, and any other relevant information that can be inferred from the diagram.

        Include any data points, labels, and other relevant information that can be inferred from the image.

        Provide a well-structured, detailed, and actionable analysis of the image. Focus on extracting data and information that can be inferred from the image.

        IMPORTANT: If the provided image is a logo or photograph, simply return 'Irrelevant Image'."""

        user_input = "Perform technical analysis on this image. Provide a well-structured, description."

        if figure.caption is not None and len(figure.caption) > 0:
            user_input += " (note: it has the following caption: {})".format(
                figure.caption
            )

        try:
            async with AsyncAzureOpenAI(
                api_key=None,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            ) as client:
                # We send both image caption and the image body to GPTv for better understanding
                response = await client.chat.completions.create(
                    model=model,
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
        except (OpenAIError, APIError, APIStatusError, BadRequestError) as e:
            logging.error(f"Failed to analyse image. Error: {e}")

            if "ResponsibleAIPolicyViolation" in e.message:
                logging.error("Responsible AI Policy Violation")
                figure.description = "Irrelevant Image"

                return figure

            raise e
        else:
            logging.info(f"Response: {response}")

            figure.description = response.choices[0].message.content

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

        logging.info(f"Record: {record}")
        figure = FigureHolder(**record["data"]["figure"])

        try:
            updated_data = await self.understand_image_with_gptv(figure)
            logging.info(f"Updated Data: {updated_data}")
        except Exception as e:
            logging.error(f"Failed to analyse image. Error: {e}")
            logging.error(f"Failed input: {record}")
            return {
                "recordId": record["recordId"],
                "data": {},
                "errors": [
                    {
                        "message": "Failed to analyse image. Pass a valid source in the request body.",
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
