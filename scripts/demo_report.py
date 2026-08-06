"""
Generates a DEMO report from MOCK data — for previewing the report design
without spending API credit. Everything here is fabricated and labelled as such.
Real audits are produced by `python -m geoaudit <url>`.

    python scripts/demo_report.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geoaudit.checks import accessibility, citability, visibility  # noqa
from geoaudit.models import AuditResult, CheckResult, Finding, ProbeRow
from geoaudit.report import render_report

# --- MOCK: a plausible local business that ranks on Google but is AI-invisible ---
probe_rows = [
    ProbeRow(
        query="best dental clinic in Chennai for implants",
        appeared=False,
        answer_excerpt="For dental implants in Chennai, frequently recommended clinics include "
                       "Clove Dental, Sabka Dentist and Dr. Smilez, known for implant expertise "
                       "and multiple branches across the city.",
        business_citations=[],
        competitor_domains=["clovedental.in", "sabkadentist.com", "drsmilez.com"],
        all_citations=["https://clovedental.in/chennai", "https://sabkadentist.com"],
    ),
    ProbeRow(
        query="affordable root canal treatment near Anna Nagar",
        appeared=False,
        answer_excerpt="Several clinics in Anna Nagar offer affordable root canal treatment, "
                       "including Partha Dental and Apollo White Dental, with prices typically "
                       "ranging from ₹4,000 to ₹8,000 depending on the tooth.",
        business_citations=[],
        competitor_domains=["parthadental.com", "apollowhitedental.com"],
        all_citations=["https://parthadental.com"],
    ),
    ProbeRow(
        query="which dentist in Chennai is good for nervous patients?",
        appeared=False,
        answer_excerpt="For anxious patients, sedation-dentistry clinics such as Clove Dental "
                       "and Thousand Smiles are often suggested for their gentle approach.",
        business_citations=[],
        competitor_domains=["clovedental.in", "thousandsmiles.in"],
        all_citations=[],
    ),
    ProbeRow(
        query="teeth whitening cost Chennai",
        appeared=True,
        answer_excerpt="Professional teeth whitening in Chennai generally costs ₹8,000–₹15,000. "
                       "Clinics like Bright Smile Dental Care and Clove Dental provide in-office "
                       "whitening with laser options.",
        business_citations=["https://brightsmilechennai.com/whitening"],
        competitor_domains=["clovedental.in"],
        all_citations=["https://brightsmilechennai.com/whitening", "https://clovedental.in"],
    ),
    ProbeRow(
        query="pediatric dentist recommendations Chennai",
        appeared=False,
        answer_excerpt="For children's dentistry in Chennai, parents commonly mention Thousand "
                       "Smiles and Kids Dental Care for their child-friendly environment.",
        business_citations=[],
        competitor_domains=["thousandsmiles.in", "kidsdentalcare.in"],
        all_citations=[],
    ),
    ProbeRow(
        query="best invisible braces / clear aligners in Chennai",
        appeared=False,
        answer_excerpt="For clear aligners in Chennai, options frequently cited include Clove "
                       "Dental (with Invisalign) and toothsi for at-home aligners.",
        business_citations=[],
        competitor_domains=["clovedental.in", "toothsi.in"],
        all_citations=[],
    ),
]

vis = CheckResult(
    key="visibility", label="AI Visibility (Share of Voice)", score=1/6, weight=50,
    summary="Do you actually appear when customers ask AI engines about your category?",
    findings=[
        Finding(
            id="share_of_voice",
            title="You appeared in 1 of 6 AI answers your customers would ask",
            status="fail",
            evidence="We asked 6 buyer-intent questions about Bright Smile Dental Care's category "
                     "(without naming you). You showed up in 1. Instead, the engine repeatedly "
                     "recommended: clovedental.in (4×), thousandsmiles.in (2×), sabkadentist.com (1×).",
            why_it_matters="This is what a customer using ChatGPT or Perplexity actually experiences "
                           "today. Every question where you don't appear is a patient handed to a "
                           "competitor — and you never see it happen.",
            fix="The Accessibility and Citability fixes below are how you climb into these answers. "
                "Start with anything blocking crawlers.",
            impact=3, effort=3,
        ),
        Finding(
            id="who_wins", title="Who AI recommends instead of you", status="info",
            evidence="Most-recommended domains across the questions: clovedental.in — cited in 4 "
                     "answer(s); thousandsmiles.in — cited in 2; sabkadentist.com — cited in 1.",
            why_it_matters="These are the clinics winning the patients who ask AI about your category.",
            impact=2, effort=3,
        ),
    ],
)

acc = CheckResult(
    key="accessibility", label="Machine Accessibility", score=0.42, weight=25,
    summary="Can AI engines reach, read, and identify this business?",
    findings=[
        Finding(
            id="robots_block",
            title="AI crawlers are blocked in robots.txt (2 of 7)",
            status="fail",
            evidence="robots.txt at https://brightsmilechennai.com/robots.txt disallows: GPTBot, "
                     "ClaudeBot. These are the exact bots that feed ChatGPT, Claude, Perplexity and "
                     "Google's AI Overviews.",
            why_it_matters="If these bots can't crawl you, the AI engines have nothing of yours to "
                           "cite. You become invisible in AI answers no matter how good your Google "
                           "ranking is.",
            fix="Allow the AI crawlers in robots.txt. Paste this block near the top:",
            fix_code=accessibility._robots_fix("https://brightsmilechennai.com"),
            impact=3, effort=1,
        ),
        Finding(
            id="schema_missing", title="No Organization schema", status="fail",
            evidence="No Organization or LocalBusiness JSON-LD found on the homepage (schema types "
                     "present: WebSite).",
            why_it_matters="Without structured identity data, AI engines have to guess who you are "
                           "from prose. Clinics with clear LocalBusiness schema are far easier to "
                           "attribute and recommend.",
            fix="Add LocalBusiness JSON-LD to your homepage <head>:",
            fix_code=accessibility._org_schema("https://brightsmilechennai.com"),
            impact=2, effort=1,
        ),
        Finding(
            id="content_ok", title="Readable content is present in the raw HTML", status="pass",
            evidence="734 words of text are in the server HTML before any JavaScript runs.",
            why_it_matters="AI crawlers can actually read what your business does.",
            impact=3, effort=3,
        ),
        Finding(
            id="llms_missing", title="No llms.txt file", status="warn",
            evidence="https://brightsmilechennai.com/llms.txt returned 404.",
            why_it_matters="llms.txt is an emerging standard (adopted by Anthropic, Stripe, "
                           "Cloudflare) that hands AI models a plain-English index of your key pages. "
                           "Cost to add is near zero.",
            fix="Create llms.txt at your site root. A starter, fill in the brackets:",
            fix_code=accessibility._llms_fix("https://brightsmilechennai.com"),
            impact=1, effort=1,
        ),
        Finding(
            id="sitemap_ok", title="Sitemap is discoverable", status="pass",
            evidence="Found a sitemap via /sitemap.xml.",
            why_it_matters="Crawlers can find all your pages, not just the ones they stumble on.",
            impact=1, effort=1,
        ),
    ],
)

cit = CheckResult(
    key="citability", label="Content Citability", score=0.33, weight=25,
    summary="If an AI can read you, is your content the kind it quotes? (Signals per Princeton GEO, KDD 2024.)",
    findings=[
        Finding(
            id="stats_low", title="Very few concrete statistics (1 across your pages)",
            status="fail",
            evidence="Found only: 2016 across ~730 words.",
            why_it_matters="AI engines quote specific, verifiable facts. Pages that say 'gentle, "
                           "affordable care' get skipped; pages that say '12,000+ patients treated "
                           "since 2016, 98% would recommend us' get cited. The Princeton GEO study "
                           "found adding statistics lifts AI visibility by up to 40%.",
            fix="Rewrite vague claims as numbers. Find your 5 strongest results and quantify them. "
                "Before → After example:",
            fix_code="BEFORE:  \"We provide gentle, affordable dental care.\"\n"
                     "AFTER:   \"We've treated 12,000+ patients since 2016 with a 98% satisfaction "
                     "rate; implants from ₹18,000, same-day crowns in under 2 hours.\"",
            impact=3, effort=2,
        ),
        Finding(
            id="faq_none", title="No FAQ / question-answer content", status="warn",
            evidence="No FAQ section, FAQPage schema, or clear question-answer blocks detected.",
            why_it_matters="People ask AI engines full questions ('what's the best implant clinic in "
                           "Chennai for nervous patients?'). Pages that answer those questions "
                           "directly, in self-contained blocks, get pulled into answers.",
            fix="Add an FAQ answering the real questions your patients ask, one clear answer each. "
                "Mark it up with FAQPage schema.",
            impact=2, effort=1,
        ),
        Finding(
            id="cite_none", title="Content cites no external authority sources", status="warn",
            evidence="No outbound links to .gov / .edu / research / industry-authority domains found.",
            why_it_matters="Counter-intuitively, linking OUT to credible sources (e.g. the Indian "
                           "Dental Association) makes AI engines more likely to cite YOU — it signals "
                           "your claims are grounded. (Princeton GEO: 'Cite Sources' was the single "
                           "most consistent visibility booster.)",
            fix="Back your key clinical claims with a link to a credible source.",
            impact=2, effort=2,
        ),
        Finding(
            id="quote_none", title="No quotations found", status="warn",
            evidence="No quoted expert statements or testimonials detected in the page text.",
            why_it_matters="Quotes from named experts/patients are a proven citation booster and add trust.",
            fix="Add 1–2 short, attributed patient/dentist quotes to key pages.",
            impact=1, effort=2,
        ),
    ],
)

result = AuditResult(
    url="https://brightsmilechennai.com",
    domain="brightsmilechennai.com",
    business_name="Bright Smile Dental Care",
    category_guess="dental clinic · Chennai",
    checks=[vis, acc, cit],
    probe_rows=probe_rows,
    engine_name="openai",
    generated_at=dt.datetime.now().strftime("%d %b %Y, %H:%M"),
    notes=[
        "DEMO REPORT — all data on this page is fabricated to preview the report design. "
        "Bright Smile Dental Care is not a real client. Run `python -m geoaudit <url>` for a live audit.",
    ],
)

os.makedirs("reports", exist_ok=True)
path = render_report(result, "reports/demo-bright-smile-dental.html")
print(f"Total: {result.total_score}/100 -> {path}")
