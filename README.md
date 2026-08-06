# GEO Auditor

**Enter a business URL. Find out whether AI search can see it — and watch it discover, live, that it can't.**

Most "AI visibility" tools scan a website and hand back a checklist: *robots.txt ✓, schema ✗, 73/100.* That tells a business owner nothing they can feel. This tool leads with the thing they can feel — **we ask a real AI engine the questions their customers ask, and show them who gets recommended instead of them** — and then explains exactly why, with the fix sitting underneath.

```
python -m geoaudit https://a-real-business.com
```

→ a single self-contained HTML report: a Share-of-AI-Voice score with receipts, a prioritized fix plan, and copy-paste snippets.

---

## Run it in under 5 minutes

```bash
git clone <this-repo> && cd geo-auditor
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then put your OpenAI key in it
#   OPENAI_API_KEY=sk-...

python -m geoaudit https://example.com
# report is written to reports/geo-audit-example-com.html — open it in a browser
```

**Just want to see the report design without spending a cent?**

```bash
python scripts/demo_report.py     # renders reports/demo-bright-smile-dental.html from MOCK data
```

Cost of a real run: the visibility probe uses OpenAI's `web_search` tool on `gpt-4.1-mini` — about **$0.01 per query + tokens**, so a full audit (≈8 queries) is a few cents. Three businesses cost well under a dollar.

---

## The one idea this is built around

GEO breaks into two halves, and almost every cheap tool does only one:

- **The symptom** — is the business *actually* absent from AI answers right now?
- **The cause** — *why*? (Can AI crawl it? Is its content the kind AI quotes?)

A checklist scanner measures proxies for the cause and never checks the symptom. So it can report "you're 68/100!" to a business that appears in **zero** AI answers. This tool measures the symptom directly, measures the cause, and **links them**: *invisible in 5 of 6 answers → because 2 crawlers are blocked, there's no Organization schema, and your pages carry 1 statistic where competitors carry 30.* That link is the product.

## The three checks — and why each one is in here

I was told to go deep on a few checks rather than wide on many, and to defend every one. Here's the defence.

### Check 1 — AI Visibility Probe · **50% of the score**
The ground truth. We profile the business from its homepage, generate 6–8 **buyer-intent questions a customer would actually type** (never naming the business, so we measure organic discovery, not a vanity lookup), and run them through a live answer engine (OpenAI + `web_search`). For each: did the business appear (in the answer text or the cited URLs)? Who appeared instead? The output is a **Share-of-AI-Voice** score plus a ranked list of the competitors the engine recommends in its place — with the exact query and answer excerpt as evidence.

*Why it's weighted highest:* it's the only check that measures what the customer experiences. It's also the check nobody can fake generic advice around — the competitor reveal is different for every business, which is exactly what the brief demanded ("report must not be identical for any website"). This is the moment the owner realises they have a problem.

### Check 2 — Machine Accessibility · **25%**
The technical cause. Machine-verifiable, every finding carries the offending line and a copy-paste fix:
- **AI-crawler access in robots.txt** for the seven bots that actually matter: `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `Claude-SearchBot`, `PerplexityBot`, `Google-Extended`. A blanket `Disallow: /` here makes a site invisible to AI while Google still ranks it — the highest-impact, lowest-effort fix in the field.
- **JS-shell detection** — AI crawlers don't run JavaScript. We fetch the *raw* server HTML and measure readable words before any JS runs. A React/Next site that renders client-side looks fine to you and to Google but is a blank page to GPTBot. Almost no consumer tool checks this; it's one of the most common silent failures.
- **Organization / LocalBusiness schema** — entity identity, including `sameAs`.
- **llms.txt** and **sitemap** discoverability.

*Why these and not "50 technical points":* these are the ones that gate citation *and* are verifiable without guessing. Each is falsifiable and comes with proof.

### Check 3 — Content Citability · **25%**
The content cause, grounded in research so it's defensible rather than vibes. The **Princeton GEO study** (Aggarwal et al., *GEO: Generative Engine Optimization*, KDD 2024; arXiv:2311.09735) tested 9 content tactics across ~10,000 queries and found three that each lift AI-answer visibility 30–40%: **adding statistics, citing sources, adding quotations.** Keyword stuffing and padding did nothing. So we measure exactly those signals on the pages an engine would read — statistic density, outbound authority citations, quotations, self-contained Q&A, freshness — and for the weak ones we hand over a concrete before/after rewrite.

*Why I trust it:* I'm not inventing signals. I'm measuring the ones a controlled 10,000-query study identified, and citing it in the report so the owner (and you) can check my reasoning.

## What I deliberately checked *and skipped*

- **Skipped: multi-engine probing.** ChatGPT, Perplexity, Gemini and AI Overviews would each give a slightly different answer. Doing one engine *properly* — with real query generation and a competitor reveal — beats querying four shallowly. The engine layer is a one-method adapter (`engines/base.py`), so adding Perplexity is a config flip, not a rewrite. A ready Perplexity adapter ships in the repo, disabled (Perplexity killed its free API credit in Feb 2026, so I won't make the default depend on paid credit).
- **Skipped: full-site crawl.** We audit the homepage + up to 4 auto-discovered key pages (about/services/pricing/products). AI citation is won on your handful of important pages, not page #400.
- **Skipped: keyword density, word count, backlink counts, PageSpeed.** These are SEO-era proxies. The Princeton study specifically found keyword density had *minimal* effect on AI citation. Measuring them would pad the report with numbers that don't move AI visibility — the opposite of the brief.
- **Skipped (correctly, per brief): auth, DB, billing, deployment, tests, mobile-responsive scraping.**

## What's real vs mocked

| Part | Status |
|---|---|
| Page fetching, JS-shell detection, robots/schema/llms/sitemap parsing | **Real** — runs against the live site |
| Citability signal extraction (stats/citations/quotes/FAQ/freshness) | **Real** — computed from fetched page text |
| Visibility probe (query generation + live answers + citations) | **Real** — live OpenAI `web_search` calls |
| Scoring & report | **Real** |
| `scripts/demo_report.py` and `reports/demo-*.html` | **Mock** — fabricated data, clearly labelled top and bottom of the report, so you can preview the design for free |

Nothing fake is ever presented as real: if the probe can't run (no key / no credit), the report says so in the honesty log and the other two checks still produce a real result.

The citability check is honestly a **proxy** for citability — transparent and reproducible, but not a claim about any one engine's internal ranking. The report says this too.

## What I'd build next with another week

1. **Multi-engine consensus** — run the same query set through OpenAI, Perplexity and Gemini, and report where you're invisible *across* engines vs. on just one. The adapter is already there.
2. **Per-query root cause** — for each question you lose, fetch the page that *should* have answered it and diff its citability signals against the competitor page that won, so the fix is page-specific.
3. **Run-to-run stability** — ask each query 3× and report an appearance rate with a confidence band, since AI answers vary.
4. **"Fix and re-check"** — apply a fix (e.g. generate the schema), let the owner deploy, re-probe in two weeks, show the movement.
5. **Answer-text brand sentiment** — when you *do* appear, is it as the recommendation or the cautionary tale?

## Project layout
```
geoaudit/
  main.py            # CLI orchestrator
  fetch.py           # crawler-eye page fetch + JS-shell detection
  profiler.py        # infer business + generate buyer-intent queries
  scoring via models.py (transparent weights: 50 / 25 / 25)
  checks/
    visibility.py    # Check 1 — the probe
    accessibility.py # Check 2 — crawlers, schema, llms.txt, sitemap
    citability.py    # Check 3 — Princeton GEO signals
  engines/           # pluggable answer engines (openai live, perplexity ready)
  report.py + templates/report.html.j2   # the product
scripts/demo_report.py    # mock-data preview
```
