from abc import ABC, abstractmethod
from pathlib import Path


class BaseTTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError