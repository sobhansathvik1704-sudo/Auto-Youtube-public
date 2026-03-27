from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_script_payload(
        self,
        topic: str,
        category: str,
        audience_level: str,
        language_mode: str,
        duration_seconds: int,
    ) -> dict:
        raise NotImplementedError