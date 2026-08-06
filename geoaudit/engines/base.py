"""
Answer-engine adapter interface.

An AnswerEngine takes a natural-language question and returns a real,
web-grounded answer plus the list of source URLs it cited — exactly what an AI
search engine (ChatGPT Search, Perplexity, AI Overviews) does. The Visibility
Probe uses this to measure whether a business actually shows up in AI answers.

Swapping engines is one line, so "add ChatGPT/Perplexity/Gemini" is a config
change, not a rewrite. We ship one engine done properly (OpenAI) and leave the
Perplexity adapter in place, disabled, for anyone with credit.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EngineAnswer:
    query: str
    answer_text: str
    cited_urls: list[str] = field(default_factory=list)
    error: str | None = None
    engine: str = ""


class AnswerEngine:
    name: str = "base"

    def ask(self, query: str) -> EngineAnswer:  # pragma: no cover - interface
        raise NotImplementedError
