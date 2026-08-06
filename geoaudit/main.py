"""
GEO Auditor — CLI entry point.

    python -m geoaudit https://example.com
    python -m geoaudit example.com --engine openai --out reports/

Runs three checks (Visibility, Accessibility, Citability), scores them
transparently, and writes a single self-contained HTML report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from urllib.parse import urlparse

from .checks import accessibility, citability, visibility
from .fetch import Page, discover_key_pages, fetch_page, normalize_url
from .models import AuditResult
from .profiler import profile_business
from .report import render_report

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass


def _build_engine(name: str):
    if name == "openai":
        from .engines.openai_engine import OpenAIEngine
        return OpenAIEngine()
    if name == "perplexity":
        from .engines.perplexity_engine import PerplexityEngine
        return PerplexityEngine()
    raise SystemExit(f"Unknown engine: {name}")


def run_audit(raw_url: str, engine_name: str = "openai", probe: bool = True) -> AuditResult:
    url = normalize_url(raw_url)
    domain = urlparse(url).netloc
    print(f"→ Fetching {url} …")
    home = fetch_page(url)
    if home.status == 0 or (home.status >= 400):
        print(f"  ! Could not fetch homepage (status {home.status}). "
              f"{home.error or ''}", file=sys.stderr)

    key_urls = discover_key_pages(home, url, limit=4)
    pages: list[Page] = [home]
    for ku in key_urls:
        print(f"→ Fetching key page {ku} …")
        pages.append(fetch_page(ku))
    pages = [p for p in pages if p.status and p.status < 400 and p.visible_text]
    if not pages:
        pages = [home]

    notes: list[str] = []

    # Profile + queries
    print("→ Profiling business and generating buyer-intent queries …")
    prof = profile_business(home)
    if prof.get("_fallback"):
        notes.append("Business profiling used a heuristic fallback (no OpenAI key), so the "
                     "generated queries are generic. Set OPENAI_API_KEY for realistic queries.")
    business_name = prof.get("business_name") or domain
    category = prof.get("category", "")
    location = prof.get("location", "")
    queries = prof.get("queries", [])

    # Check 1 — Visibility probe
    probe_rows = []
    if probe and queries:
        try:
            engine = _build_engine(engine_name)
            print(f"→ Running visibility probe on {len(queries)} queries via {engine_name} …")
            vis_result, probe_rows = visibility.run(
                engine, domain, business_name, queries
            )
            notes.append(
                f"Visibility measured with {engine_name} + live web search as a stand-in for a "
                f"consumer AI engine. AI answers vary run to run; treat share-of-voice as a strong "
                f"signal, not a fixed number."
            )
        except Exception as e:
            print(f"  ! Visibility probe skipped: {e}", file=sys.stderr)
            from .models import CheckResult, Finding
            vis_result = CheckResult(
                key="visibility", label="AI Visibility (Share of Voice)", score=0.0, weight=50,
                findings=[Finding(
                    id="probe_skip", title="Visibility probe skipped", status="info",
                    evidence=str(e),
                    why_it_matters="Add engine API credentials and re-run to measure real AI visibility.",
                )],
                summary="Do you actually appear when customers ask AI engines about your category?",
            )
            notes.append(f"Visibility probe skipped: {e}")
    else:
        from .models import CheckResult, Finding
        vis_result = CheckResult(
            key="visibility", label="AI Visibility (Share of Voice)", score=0.0, weight=50,
            findings=[Finding(id="probe_off", title="Visibility probe disabled", status="info",
                              evidence="Run without --no-probe and with an engine key to measure this.",
                              why_it_matters="This is the check that shows whether you actually appear in AI answers.")],
            summary="Do you actually appear when customers ask AI engines about your category?",
        )

    # Check 2 — Accessibility
    print("→ Checking machine accessibility (crawlers, schema, llms.txt) …")
    acc_result = accessibility.run(home, url)

    # Check 3 — Citability
    print("→ Analysing content citability (Princeton GEO signals) …")
    from .checks.visibility import registrable
    cit_result = citability.run(pages, registrable(domain))

    result = AuditResult(
        url=url, domain=domain, business_name=business_name,
        category_guess=(f"{category} · {location}".strip(" ·") if category else ""),
        checks=[vis_result, acc_result, cit_result],
        probe_rows=probe_rows, engine_name=engine_name,
        generated_at=dt.datetime.now().strftime("%d %b %Y, %H:%M"),
        notes=notes,
    )
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="GEO Auditor — is a business visible in AI search?")
    ap.add_argument("url", help="Business website URL")
    ap.add_argument("--engine", default="openai", choices=["openai", "perplexity"])
    ap.add_argument("--out", default="reports", help="Output directory")
    ap.add_argument("--no-probe", action="store_true", help="Skip the live AI visibility probe")
    args = ap.parse_args(argv)

    result = run_audit(args.url, engine_name=args.engine, probe=not args.no_probe)

    os.makedirs(args.out, exist_ok=True)
    slug = urlparse(result.url).netloc.replace(".", "-")
    out_path = os.path.join(args.out, f"geo-audit-{slug}.html")
    render_report(result, out_path)
    print(f"\n✓ Score: {result.total_score}/100  →  report written to {out_path}")


if __name__ == "__main__":
    main()
