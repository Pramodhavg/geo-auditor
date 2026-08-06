"""
OpenAI answer engine — uses the Responses API with the built-in `web_search`
tool so the model retrieves live web results and answers with real citations,
mimicking how ChatGPT Search picks and cites sources.

Model default: gpt-4.1-mini (cheap; officially supports the non-preview
web_search tool). Override with OPENAI_MODEL. Cost is ~$0.01/search + tokens,
so a full 3-business audit runs for well under a dollar.
"""
from __future__ import annotations

import os
import re

from .base import AnswerEngine, EngineAnswer

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# Ask the engine to behave like a consumer asking a real question — no mention
# of the business, so we get an unbiased read on who it surfaces on its own.
SYSTEM_PROMPT = (
    "You are a helpful web search assistant. Answer the user's question the way "
    "an AI answer engine would: search the web, then give a concise, practical "
    "answer naming specific businesses, brands, or products where relevant. "
    "Cite the sources you used."
)


class OpenAIEngine(AnswerEngine):
    name = "openai"

    def __init__(self, model: str = DEFAULT_MODEL):
        from openai import OpenAI  # imported lazily so the tool loads without the key

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to your environment or .env")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def ask(self, query: str) -> EngineAnswer:
        try:
            resp = self.client.responses.create(
                model=self.model,
                tools=[{"type": "web_search"}],
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
            )
        except Exception as e:  # network/credit/model errors surface in the report
            return EngineAnswer(query=query, answer_text="", error=str(e), engine=self.name)

        text = getattr(resp, "output_text", "") or ""
        urls = self._extract_citations(resp, text)
        return EngineAnswer(
            query=query, answer_text=text, cited_urls=urls, engine=self.name
        )

    @staticmethod
    def _extract_citations(resp, text: str) -> list[str]:
        """Pull cited URLs from url_citation annotations, falling back to regex."""
        urls: list[str] = []
        try:
            for item in resp.output:
                for block in getattr(item, "content", []) or []:
                    for ann in getattr(block, "annotations", []) or []:
                        u = getattr(ann, "url", None)
                        if u:
                            urls.append(u)
        except Exception:
            pass
        if not urls:
            urls = re.findall(r"https?://[^\s\)\]\"'>]+", text)
        # dedupe, preserve order
        seen, out = set(), []
        for u in urls:
            u = u.rstrip(".,);]")
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out
