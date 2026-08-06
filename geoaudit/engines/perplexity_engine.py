"""
Perplexity Sonar answer engine — OPTIONAL / OFF BY DEFAULT.

Perplexity's Sonar API returns the cleanest citation URLs of any engine, which
makes it ideal evidence. But Perplexity has no reliable free tier (the $5/month
Pro API credit was discontinued in Feb 2026), so we don't depend on it. This
adapter is complete and drop-in: set PERPLEXITY_API_KEY and pass
--engine perplexity to use it.
"""
from __future__ import annotations

import os

import requests

from .base import AnswerEngine, EngineAnswer

ENDPOINT = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar")


class PerplexityEngine(AnswerEngine):
    name = "perplexity"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise RuntimeError("PERPLEXITY_API_KEY is not set.")
        self.model = model

    def ask(self, query: str) -> EngineAnswer:
        try:
            r = requests.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Answer concisely, naming specific businesses/brands. Cite sources."},
                        {"role": "user", "content": query},
                    ],
                },
                timeout=45,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return EngineAnswer(query=query, answer_text="", error=str(e), engine=self.name)

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        urls = data.get("citations") or data.get("search_results") or []
        # citations may be list[str] or list[dict]
        cited = [u if isinstance(u, str) else u.get("url", "") for u in urls]
        return EngineAnswer(
            query=query, answer_text=text, cited_urls=[u for u in cited if u], engine=self.name
        )
