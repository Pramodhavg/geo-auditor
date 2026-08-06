"""
Check 3 — Citability of the content.

Once an AI engine CAN read you (Check 2), will it WANT to quote you? The
Princeton GEO study (Aggarwal et al., "GEO: Generative Engine Optimization",
KDD 2024; arXiv:2311.09735) tested 9 content tactics across ~10,000 queries and
found three that each lifted AI-answer visibility by 30–40%:

  1. Statistics Addition  — concrete numbers beat vague claims
  2. Cite Sources         — linking out to credible sources makes YOU more citable
  3. Quotation Addition   — direct, attributable quotes signal grounded content

Keyword stuffing and content padding did nothing. So we don't count keywords.
We measure exactly the signals the research says move the needle, on the pages
an AI engine would actually read. Every signal is defensible by citation.

This check is deliberately a *proxy* for citability, computed from on-page text.
It is transparent and reproducible; it is not a claim about a specific engine's
internal ranking.
"""
from __future__ import annotations

import re

from ..fetch import Page
from ..models import CheckResult, Finding

# credible / authority outbound domains (not socials, not the site's own domain)
AUTHORITY_HINTS = (".gov", ".edu", ".org", "wikipedia.org", "reuters.", "nature.",
                   "who.int", "nih.gov", "statista.", "gartner.", "mckinsey.")

STAT_RE = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?\s?%|\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\s?(?:x|percent|million|billion|k)\b|\b(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)
QUOTE_RE = re.compile(r"[\u201c\u201d\"]([^\"\u201c\u201d]{25,300})[\u201c\u201d\"]")


def _count_stats(text: str) -> list[str]:
    hits = STAT_RE.findall(text)
    # findall with groups returns tuples of the alternation; flatten
    flat = [h if isinstance(h, str) else next((g for g in h if g), "") for h in hits]
    return [h for h in flat if h.strip()]


def _count_outbound_authority(page: Page, base_domain: str) -> list[str]:
    if not page.soup:
        return []
    out = []
    for a in page.soup.find_all("a", href=True):
        href = a["href"].lower()
        if href.startswith("http") and base_domain not in href:
            if any(h in href for h in AUTHORITY_HINTS):
                out.append(a["href"])
    return list(dict.fromkeys(out))


def _has_faq(page: Page) -> bool:
    if not page.soup:
        return False
    if page.soup.find("script", string=re.compile("FAQPage")):
        return True
    text = page.visible_text.lower()
    q_marks = page.visible_text.count("?")
    faq_words = any(w in text for w in ("frequently asked", "faq"))
    return faq_words or q_marks >= 4


def _freshness(page: Page) -> str | None:
    if not page.soup:
        return None
    for tag in page.soup.find_all("meta"):
        prop = (tag.get("property") or tag.get("name") or "").lower()
        if prop in ("article:modified_time", "og:updated_time", "datemodified", "last-modified"):
            return tag.get("content")
    t = page.soup.find("time")
    if t and t.get("datetime"):
        return t["datetime"]
    return None


def run(pages: list[Page], base_domain: str) -> CheckResult:
    corpus = " ".join(p.visible_text for p in pages)
    words = max(len(corpus.split()), 1)
    home = pages[0]

    stats = _count_stats(corpus)
    authority_links: list[str] = []
    for p in pages:
        authority_links.extend(_count_outbound_authority(p, base_domain))
    authority_links = list(dict.fromkeys(authority_links))
    quotes = QUOTE_RE.findall(corpus)
    has_faq = any(_has_faq(p) for p in pages)
    fresh = next((f for f in (_freshness(p) for p in pages) if f), None)

    findings: list[Finding] = []

    # 1. Statistics
    density = len(stats) / (words / 500)  # stats per ~500 words
    if len(stats) >= 5 and density >= 1:
        findings.append(Finding(
            id="stats_ok", title=f"Content carries concrete statistics ({len(stats)} found)",
            status="pass",
            evidence="Examples on your pages: " + ", ".join(f'"{s}"' for s in stats[:5]),
            why_it_matters="Specific numbers are one of the strongest AI-citation signals (Princeton GEO, KDD 2024: +30–40%).",
            impact=3, effort=2,
        ))
    else:
        findings.append(Finding(
            id="stats_low", title=f"Very few concrete statistics ({len(stats)} across your pages)",
            status="fail" if len(stats) < 2 else "warn",
            evidence=(
                (f"Found only: {', '.join(stats)} " if stats else "No numeric data points found ")
                + f"across ~{words} words."
            ),
            why_it_matters=(
                "AI engines quote specific, verifiable facts. Pages that say 'we help many clients "
                "save money' get skipped; pages that say 'we've cut invoice processing time 63% for "
                "40+ SMBs' get cited. The Princeton GEO study found adding statistics lifts AI "
                "visibility by up to 40%."
            ),
            fix=(
                "Rewrite vague claims as numbers. Find your 5 strongest results and quantify them. "
                "Before → After example:"
            ),
            fix_code=(
                "BEFORE:  \"We help small businesses save time on invoicing.\"\n"
                "AFTER:   \"We cut invoice processing time by 63% on average across 40+ SMB "
                "clients, from ~12 minutes to under 5 per invoice (2025 data).\""
            ),
            impact=3, effort=2,
        ))

    # 2. Cite sources (outbound authority)
    if authority_links:
        findings.append(Finding(
            id="cite_ok", title=f"Content cites credible external sources ({len(authority_links)})",
            status="pass",
            evidence="e.g. " + ", ".join(authority_links[:3]),
            why_it_matters="Citing credible sources makes your own content read as verified — a top-3 GEO signal.",
            impact=2, effort=2,
        ))
    else:
        findings.append(Finding(
            id="cite_none", title="Content cites no external authority sources", status="warn",
            evidence="No outbound links to .gov / .edu / research / industry-authority domains were found.",
            why_it_matters=(
                "Counter-intuitively, linking OUT to credible sources makes AI engines more likely "
                "to cite YOU — it signals your claims are grounded, not marketing. (Princeton GEO: "
                "'Cite Sources' was the single most consistent visibility booster.)"
            ),
            fix="Back your key claims with a link to a credible source (industry report, standards body, research).",
            impact=2, effort=2,
        ))

    # 3. Quotations
    if len(quotes) >= 1:
        findings.append(Finding(
            id="quote_ok", title=f"Attributable quotes present ({len(quotes)})", status="pass",
            evidence="e.g. " + " / ".join(f'"{q[:80]}…"' for q in quotes[:2]),
            why_it_matters="Direct quotes signal grounded, credible content (Princeton GEO top-3 tactic).",
            impact=1, effort=2,
        ))
    else:
        findings.append(Finding(
            id="quote_none", title="No quotations found", status="warn",
            evidence="No quoted expert statements or testimonials detected in the page text.",
            why_it_matters="Quotes from named experts/clients are a proven citation booster and add trust.",
            fix="Add 1–2 short, attributed quotes (a client result, an expert take) to key pages.",
            impact=1, effort=2,
        ))

    # 4. Self-contained Q&A / FAQ
    if has_faq:
        findings.append(Finding(
            id="faq_ok", title="Question-and-answer content present", status="pass",
            evidence="Found FAQ schema or a Q&A structure on your pages.",
            why_it_matters="AI engines lift self-contained answers to specific questions. Q&A blocks are prime citation fodder.",
            impact=2, effort=1,
        ))
    else:
        findings.append(Finding(
            id="faq_none", title="No FAQ / question-answer content", status="warn",
            evidence="No FAQ section, FAQPage schema, or clear question-answer blocks detected.",
            why_it_matters=(
                "People ask AI engines full questions ('what's the best X in Y for Z?'). Pages that "
                "answer those questions directly, in self-contained blocks, get pulled into answers."
            ),
            fix="Add an FAQ answering the real questions your customers ask, one clear answer each. Mark it up with FAQPage schema.",
            impact=2, effort=1,
        ))

    # 5. Freshness
    if fresh:
        findings.append(Finding(
            id="fresh_ok", title="Content signals a recent update date", status="pass",
            evidence=f"Detected a modified/published date signal: {fresh}",
            why_it_matters="AI engines favour fresh content; a visible recent date helps.",
            impact=1, effort=1,
        ))
    else:
        findings.append(Finding(
            id="fresh_none", title="No visible freshness/date signal", status="info",
            evidence="No dateModified / updated-time metadata found on the pages checked.",
            why_it_matters="A visible 'last updated' date is a small, easy freshness signal for AI engines.",
            fix="Expose a dateModified in your page metadata and show 'Last updated' on key pages.",
            impact=1, effort=1,
        ))

    score = _score(findings)
    return CheckResult(
        key="citability", label="Content Citability", score=score, weight=25,
        findings=findings,
        summary="If an AI can read you, is your content the kind it quotes? (Signals per Princeton GEO, KDD 2024.)",
    )


def _score(findings: list[Finding]) -> float:
    weights = {"fail": 0.0, "warn": 0.5, "pass": 1.0, "info": 0.75}
    total = sum(f.impact for f in findings)
    got = sum(weights[f.status] * f.impact for f in findings)
    return round(got / total, 3) if total else 0.0
