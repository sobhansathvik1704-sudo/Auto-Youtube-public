from app.core.config import get_settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.local_provider import LocalLLMProvider

settings = get_settings()


def get_llm_provider() -> BaseLLMProvider:
    if settings.llm_provider == "openai":
        from app.services.llm.openai_provider import OpenAILLMProvider
        return OpenAILLMProvider()
    return LocalLLMProvider()
