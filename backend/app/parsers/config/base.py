from abc import ABC, abstractmethod
from typing import List, Dict, Any


class IConfigParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: str) -> Dict[str, Any]:
        pass
