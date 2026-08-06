"""
Check 1 — AI Visibility Probe (the ground truth).

Everything else in this audit explains WHY a business might be invisible. This
check measures WHETHER it actually is. We ask a live answer engine the questions
a real customer would ask — never naming the business — and check whether the
business shows up, and who shows up instead.

Output: a Share-of-AI-Voice score with receipts (the exact query, the answer
excerpt, the citations) and the competitors the engine recommends in its place.
That competitor reveal is the moment the owner realises they have a problem.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..engines.base import AnswerEngine
from ..models import CheckResult, Finding, ProbeRow

# Platforms that are usually not "competitors" — infrastructure/aggregators.
NON_COMPETITOR = {
    "wikipedia.org", "youtube.com", "facebook.com", "instagram.com", "linkedin.com",
    "reddit.com", "quora.com", "medium.com", "x.com", "twitter.com", "pinterest.com",
    "yelp.com", "tripadvisor.com", "google.com", "apple.com",
}


_COMPOUND_SUFFIXES = {
    "co.in","co.uk","com.au","co.jp","co.nz","co.za","com.br","com.sg",
    "com.my","co.id","org.uk","gov.in","ac.in","net.in","org.in","com.mx",
    "co.kr","com.hk","com.tr","com.ph","co.th","com.cn","co.il","com.pk",
    "org.au","net.au","gov.uk","ac.uk",
}


def registrable(host: str) -> str:
    host = host.lower().split(":")[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _COMPOUND_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _domain_of(url: str) -> str:
    try:
        return registrable(urlparse(url).netloc)
    except Exception:
        return ""


def run(engine: AnswerEngine, business_domain: str, business_name: str,
        queries: list[str]) -> tuple[CheckResult, list[ProbeRow]]:
    biz_dom = registrable(business_domain)
    name_l = (business_name or "").lower().strip()
    rows: list[ProbeRow] = []

    for q in queries:
        ans = engine.ask(q)
        if ans.error:
            rows.append(ProbeRow(query=q, appeared=False, answer_excerpt="",
                                 business_citations=[], competitor_domains=[],
                                 all_citations=[], error=ans.error))
            continue

        cited_domains = [_domain_of(u) for u in ans.cited_urls]
        biz_citations = [u for u in ans.cited_urls if _domain_of(u) == biz_dom]
        name_hit = bool(name_l) and len(name_l) > 2 and name_l in ans.answer_text.lower()
        appeared = bool(biz_citations) or name_hit

        competitors = []
        for d in cited_domains:
            if d and d != biz_dom and d not in NON_COMPETITOR and d not in competitors:
                competitors.append(d)

        excerpt = ans.answer_text.strip().replace("\n", " ")
        if len(excerpt) > 320:
            excerpt = excerpt[:320].rsplit(" ", 1)[0] + "…"

        rows.append(ProbeRow(
            query=q, appeared=appeared, answer_excerpt=excerpt,
            business_citations=biz_citations, competitor_domains=competitors[:5],
            all_citations=ans.cited_urls,
        ))

    valid = [r for r in rows if r.error is None]
    appeared_count = sum(1 for r in valid if r.appeared)
    total = len(valid)
    score = (appeared_count / total) if total else 0.0

    # Rank the competitors that recur most across answers.
    tally: dict[str, int] = {}
    for r in valid:
        for d in r.competitor_domains:
            tally[d] = tally.get(d, 0) + 1
    top_competitors = sorted(tally.items(), key=lambda kv: -kv[1])[:6]

    findings: list[Finding] = []
    if total == 0:
        findings.append(Finding(
            id="probe_error", title="Visibility probe could not run", status="info",
            evidence="; ".join(dict.fromkeys(r.error or "" for r in rows if r.error))[:400] or "No answers returned.",
            why_it_matters="Check your engine API key/credit and re-run. The rest of the audit still applies.",
            impact=1, effort=1,
        ))
    else:
        headline_status = "pass" if score >= 0.5 else ("warn" if score > 0 else "fail")
        comp_txt = ""
        if top_competitors:
            comp_txt = (
                " Instead, the engine repeatedly recommended: "
                + ", ".join(f"{d} ({n}×)" for d, n in top_competitors) + "."
            )
        findings.append(Finding(
            id="share_of_voice",
            title=f"You appeared in {appeared_count} of {total} AI answers your customers would ask",
            status=headline_status,
            evidence=(
                f"We asked {total} buyer-intent questions about '{business_name}'s category "
                f"(without naming you). You showed up in {appeared_count}." + comp_txt
            ),
            why_it_matters=(
                "This is what a customer using ChatGPT or Perplexity actually experiences today. "
                "Every question where you don't appear is a customer handed to a competitor — "
                "and you never see it happen."
            ),
            fix=(
                "The Accessibility and Citability fixes below are how you climb into these answers. "
                "Start with anything blocking crawlers, then make the pages that should answer "
                "these questions concrete and quotable."
            ),
            impact=3, effort=3,
        ))
        # Per-competitor finding for the emotional punch, with proof.
        if top_competitors:
            findings.append(Finding(
                id="who_wins", title="Who AI recommends instead of you", status="info",
                evidence="Most-recommended domains across the questions: "
                         + "; ".join(f"{d} — cited in {n} answer(s)" for d, n in top_competitors),
                why_it_matters="These are the businesses winning the customers who ask AI about your category.",
                impact=2, effort=3,
            ))

    result = CheckResult(
        key="visibility", label="AI Visibility (Share of Voice)", score=score, weight=50,
        findings=findings,
        summary="Do you actually appear when customers ask AI engines about your category?",
    )
    return result, rows
