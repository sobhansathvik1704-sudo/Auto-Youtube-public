from app.services.ai.llm import LLMClient
from app.services.llm.base import BaseLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
    """LLM provider implementation backed by OpenAI GPT models."""

    def __init__(self) -> None:
        self._client = LLMClient()

    def generate_script_payload(
        self,
        topic: str,
        category: str,
        audience_level: str,
        language_mode: str,
        duration_seconds: int,
    ) -> dict:
        return self._client.generate_script_from_topic(
            topic=topic,
            niche=category,
            language=language_mode,
            duration_seconds=duration_seconds,
            audience_level=audience_level,
        )
