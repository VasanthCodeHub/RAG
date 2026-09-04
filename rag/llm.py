import logging
import os
from abc import ABC

import google.api_core.exceptions
import google.generativeai as genai
from groq import Groq

logger = logging.getLogger("rag.llm")


class BaseLLM(ABC):

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, **kwargs):
        raise NotImplementedError

    def chat(self, prompt: str, **kwargs):
        raise NotImplementedError

    def generate_with_reasoning(self, prompt: str, **kwargs) -> dict:
        """Like generate(), but also returns the model's reasoning/chain-of-
        thought text when the underlying model exposes one. Default
        implementation just wraps generate() with reasoning=None; only
        models that actually support it (e.g. GroqLLM with a reasoning
        model) override this.
        """
        return {"content": self.generate(prompt, **kwargs), "reasoning": None}


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
        for attempt in range(1, max_retries + 1):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except (google.api_core.exceptions.InternalServerError, Exception) as error:
                last_error = error
                logger.warning(
                    "gemini generate attempt=%d/%d failed error=%r",
                    attempt,
                    max_retries,
                    error,
                )
        logger.error(
            "gemini generate failed after %d attempts error=%r", max_retries, last_error
        )
        raise RuntimeError(
            f"Gemini request failed after {max_retries} attempts"
        ) from last_error

    def chat(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)


class GroqLLM(BaseLLM):
    def __init__(self, *args, **kwargs):
        """Initialize the Groq-hosted language model.
        - api_key: str: The API key for the Groq API. Falls back to GROQ_API_KEY.
        - model_name: str: The Groq model to use. Defaults to "openai/gpt-oss-120b".
        """
        super().__init__(*args, **kwargs)
        api_key = os.getenv("GROQ_API_KEY") or kwargs.get("api_key")
        if not api_key:
            raise ValueError(
                "Please set GROQ_API_KEY environment variable or set api_key."
            )
        self.client = Groq(api_key=api_key)
        self.model_name = kwargs.get("model_name", "openai/gpt-oss-120b")

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from the model.
        - prompt: str: The prompt to generate text from.
        - max_retries: int: How many times to retry on failure.
        """
        return self.generate_with_reasoning(prompt, **kwargs)["content"]

    def generate_with_reasoning(self, prompt: str, **kwargs) -> dict:
        """Like generate(), but also returns the model's reasoning trace.
        Only `gpt-oss` Groq models currently support `reasoning_format`, so
        it's only requested for those -- other models just come back with
        reasoning=None.
        - prompt: str: The prompt to generate text from.
        - max_retries: int: How many times to retry on failure.
        """
        max_retries = kwargs.get("max_retries", 3)
        request_kwargs = dict(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        if "gpt-oss" in self.model_name:
            request_kwargs["reasoning_format"] = "parsed"

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(**request_kwargs)
                message = response.choices[0].message
                return {
                    "content": message.content,
                    "reasoning": getattr(message, "reasoning", None),
                }
            except Exception as error:
                last_error = error
                logger.warning(
                    "groq generate attempt=%d/%d model=%r failed error=%r",
                    attempt,
                    max_retries,
                    self.model_name,
                    error,
                )
        logger.error(
            "groq generate failed after %d attempts model=%r error=%r",
            max_retries,
            self.model_name,
            last_error,
        )
        raise RuntimeError(
            f"Groq request failed after {max_retries} attempts"
        ) from last_error

    def chat(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)
