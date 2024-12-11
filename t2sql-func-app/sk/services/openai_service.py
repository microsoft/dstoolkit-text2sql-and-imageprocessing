# python
import openai
import os


class OpenAIService:
    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        openai.api_key = self.api_key

    def get_response(self, prompt: str) -> str:
        """
        Generates a response from OpenAI based on the given prompt.

        Args:
            prompt (str): The prompt to send to the OpenAI API.

        Returns:
            str: The response text from OpenAI.
        """
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=150
        )
        return response.choices[0].text.strip()

    