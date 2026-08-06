"""
Profile a business from its homepage and generate the questions a real customer
would ask an AI engine — WITHOUT naming the business, so the probe measures
genuine organic discovery, not a vanity lookup.

Uses a cheap OpenAI text call (no web search). Falls back to heuristics if no
key is available, so the tool still runs.
"""
from __future__ import annotations

import json
import os

from .fetch import Page

PROFILE_MODEL = os.getenv("OPENAI_PROFILE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

PROMPT = """You are analysing a business from its website text to prepare an AI-search visibility test.

From the homepage content below, return STRICT JSON with:
- "business_name": the business's name
- "category": short category a customer would search (e.g. "dental clinic", "invoice automation software")
- "location": city/region if it's a local business, else "" (empty)
- "queries": 8 natural questions a potential CUSTOMER would ask ChatGPT/Perplexity when looking for a business like this. CRITICAL RULES for queries:
  - Do NOT mention this business's name. We are testing whether it gets discovered on its own.
  - Write them the way a real buyer types: "best {category} in {location}", "affordable ... for ...", "what's a good ... that ...", comparison and recommendation questions.
  - Mix local and non-local if relevant. Make them specific and realistic.

Return ONLY the JSON object, no prose.

HOMEPAGE TEXT:
\"\"\"
{content}
\"\"\"
"""


def _heuristic(home: Page) -> dict:
    name = home.title.split("|")[0].split("-")[0].strip() or home.h1 or home.url
    return {
        "business_name": name,
        "category": "business",
        "location": "",
        "queries": [
            f"What are the best options similar to {name}?",
            f"Recommend a good provider like {name}.",
        ],
        "_fallback": True,
    }


def profile_business(home: Page) -> dict:
    content = (home.visible_text or "")[:6000]
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not content:
        return _heuristic(home)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=PROFILE_MODEL,
            messages=[{"role": "user", "content": PROMPT.replace("{content}", content)}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content)
        data.setdefault("queries", [])
        data["queries"] = [q for q in data["queries"] if isinstance(q, str)][:8]
        if not data["queries"]:
            return _heuristic(home)
        return data
    except Exception:
        return _heuristic(home)
