import os
from abc import ABC

import google.api_core.exceptions
import google.generativeai as genai


class BaseLLM(ABC):

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, **kwargs):
        raise NotImplementedError

    def chat(self, prompt: str, **kwargs):
        raise NotImplementedError


class GeminiLLM(BaseLLM):
    def __init__(self, *args, **kwargs):
        """Initialize the Gemini language model.
        - api_key: str: The API key for the Gemini API. Falls back to GOOGLE_API_KEY.
        - model_name: str: The Gemini model to use. Defaults to "gemini-flash-latest".
        """
        super().__init__(*args, **kwargs)
        api_key = os.getenv("GOOGLE_API_KEY") or kwargs.get("api_key")
        if not api_key:
            raise ValueError(
                "Please set GOOGLE_API_KEY environment variable or set api_key."
            )
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            kwargs.get("model_name", "gemini-flash-latest"),
            generation_config=genai.GenerationConfig(temperature=0.0),
        )

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from the model.
        - prompt: str: The prompt to generate text from.
        - max_retries: int: How many times to retry on failure.
        """
        max_retries = kwargs.get("max_retries", 3)
        last_error = None
        for _ in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except (google.api_core.exceptions.InternalServerError, Exception) as error:
                last_error = error
        raise RuntimeError(
            f"Gemini request failed after {max_retries} attempts"
        ) from last_error

    def chat(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)
