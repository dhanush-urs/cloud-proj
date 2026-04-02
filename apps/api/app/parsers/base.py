from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    language: str = "Unknown"

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_path: Path) -> dict:
        raise NotImplementedError
