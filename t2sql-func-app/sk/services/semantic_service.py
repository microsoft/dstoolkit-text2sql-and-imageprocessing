from semantic_kernel import Kernel
from openai_service import OpenAIService


class SemanticService:
    def __init__(self):
        self.kernel = Kernel()
        self.openai_service = OpenAIService()
        self.sql_plugin = self.kernel.load_plugin("sql")  # Load SQL plugin

    def process(self, input_text: str) -> str:
        # Determine the plugin to use based on input_text
        plugin = self.kernel.determine_plugin(input_text)
        if plugin == "sql":
            sql_result = self.sql_plugin.execute(input_text)
            # Use Chat service with the SQL result
            chat_response = self.openai_service.get_response(sql_result)
            return chat_response
        else:
            return "Unsupported plugin."
