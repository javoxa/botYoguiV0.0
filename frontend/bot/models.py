from dataclasses import dataclass
from enum import Enum
from typing import List

class ResponseMode(Enum):
    DIRECT = "direct"
    LLM = "llm"
    FALLBACK = "fallback"

@dataclass
class SearchResult:
    id: int
    content: str
    category: str
    faculty: str
    score: float
    keywords: List[str]
