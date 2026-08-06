"""
Check 2 — Machine Accessibility.

Can AI engines physically reach, read, and identify this business? This is the
"cause" layer for technical invisibility. A site can rank #1 on Google and be
blocked from every AI crawler and never know it.

We check the things that are (a) machine-verifiable with proof and (b) known to
gate AI citation:
  - robots.txt rules for the real AI user-agents
  - whether the raw HTML actually contains readable content (JS-shell trap)
  - Organization / LocalBusiness schema (entity identity)
  - llms.txt (emerging AI index file)
  - sitemap discoverability
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

import requests

from ..fetch import CRAWLER_UA, Page, http_get
from ..models import CheckResult, Finding

TIMEOUT = 15

# The AI crawlers that matter for citation, grouped by owner.
AI_BOTS = [
    ("GPTBot", "OpenAI — trains + powers ChatGPT retrieval"),
    ("OAI-SearchBot", "OpenAI — ChatGPT Search index"),
    ("ChatGPT-User", "OpenAI — live fetch when ChatGPT browses"),
    ("ClaudeBot", "Anthropic — Claude"),
    ("Claude-SearchBot", "Anthropic — Claude search"),
    ("PerplexityBot", "Perplexity"),
    ("Google-Extended", "Google — Gemini / AI Overviews training"),
]


def _fetch_text(url: str) -> tuple[int, str]:
    try:
        r = http_get(url)
        return r.status_code, r.text or ""
    except requests.RequestException:
        return 0, ""


def _parse_robots(text: str) -> dict[str, list[str]]:
    """Return {user_agent_lower: [disallow paths]} grouped correctly."""
    groups: dict[str, list[str]] = {}
    current_agents: list[str] = []
    prev_was_rule = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower(); value = value.strip()
        if field == "user-agent":
            if prev_was_rule:
                current_agents = []; prev_was_rule = False
            current_agents.append(value.lower())
            groups.setdefault(value.lower(), [])
        elif field == "disallow" and current_agents:
            for ua in current_agents:
                groups.setdefault(ua, []).append(value)
            prev_was_rule = True
        elif field == "allow" and current_agents:
            prev_was_rule = True
    return groups


def _is_blocked(groups: dict[str, list[str]], bot: str) -> bool:
    """A bot is 'blocked' if its group (or the * group it falls under) disallows /."""
    ua = bot.lower()
    rules = groups.get(ua)
    if rules is None:
        rules = groups.get("*")  # falls under the catch-all
    if not rules:
        return False
    # Disallow: /  (or Disallow: with an empty value means "allow all")
    return any(r == "/" for r in rules)


def run(home: Page, base_url: str) -> CheckResult:
    findings: list[Finding] = []
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"

    # --- robots.txt / AI crawler access -----------------------------------
    r_status, robots_text = _fetch_text(urljoin(root + "/", "robots.txt"))
    if r_status == 200 and "<html" in robots_text[:600].lower():
        robots_text = ""
    if r_status == 200 and robots_text.strip():
        groups = _parse_robots(robots_text)
        blocked = [(b, why) for b, why in AI_BOTS if _is_blocked(groups, b)]
        if blocked:
            names = ", ".join(b for b, _ in blocked)
            findings.append(Finding(
                id="robots_block",
                title=f"AI crawlers are blocked in robots.txt ({len(blocked)} of {len(AI_BOTS)})",
                status="fail",
                evidence=(
                    f"robots.txt at {root}/robots.txt disallows: {names}. "
                    f"These are the exact bots that feed ChatGPT, Claude, Perplexity and "
                    f"Google's AI Overviews."
                ),
                why_it_matters=(
                    "If these bots can't crawl you, the AI engines have nothing of yours to "
                    "cite. You become invisible in AI answers no matter how good your Google "
                    "ranking is."
                ),
                fix="Allow the AI crawlers in robots.txt. Paste this block near the top:",
                fix_code=_robots_fix(root),
                impact=3, effort=1,
            ))
        else:
            findings.append(Finding(
                id="robots_ok",
                title="AI crawlers are allowed in robots.txt",
                status="pass",
                evidence=f"No blanket Disallow found for {', '.join(b for b,_ in AI_BOTS)} at {root}/robots.txt.",
                why_it_matters="The major AI engines can physically reach your pages.",
                impact=3, effort=1,
            ))
    else:
        findings.append(Finding(
            id="robots_missing",
            title="No robots.txt found",
            status="warn",
            evidence=f"{root}/robots.txt returned status {r_status or 'no response'}.",
            why_it_matters=(
                "Missing robots.txt usually means crawlers aren't blocked, which is fine — but "
                "you also can't point them to your sitemap. Add one to stay in control."
            ),
            fix="Create robots.txt at your site root with:",
            fix_code=_robots_fix(root),
            impact=1, effort=1,
        ))

    # --- JS-shell / content extractability --------------------------------
    if home.is_js_shell:
        findings.append(Finding(
            id="js_shell",
            title="Your homepage is nearly empty to an AI crawler",
            status="fail",
            evidence=home.js_shell_reason,
            why_it_matters=(
                "AI crawlers don't run JavaScript. If your content is drawn by JS after load, "
                "they see a blank page — even though it looks fine to you and to Google. This is "
                "one of the most common silent causes of AI invisibility."
            ),
            fix=(
                "Serve real HTML content on first load (server-side render or pre-render your "
                "key pages). At minimum, make sure your homepage's core text — what you do, for "
                "whom, where — is present in 'View Source', not injected later."
            ),
            impact=3, effort=3,
        ))
    else:
        findings.append(Finding(
            id="content_ok",
            title="Readable content is present in the raw HTML",
            status="pass",
            evidence=f"{home.word_count} words of text are in the server HTML before any JavaScript runs.",
            why_it_matters="AI crawlers can actually read what your business does.",
            impact=3, effort=3,
        ))

    # --- Organization schema ----------------------------------------------
    findings.append(_schema_finding(home, root))

    # --- llms.txt ----------------------------------------------------------
    l_status, l_text = _fetch_text(urljoin(root + "/", "llms.txt"))
    if l_status == 200 and len(l_text.strip()) > 40:
        findings.append(Finding(
            id="llms_ok", title="llms.txt is present", status="pass",
            evidence=f"{root}/llms.txt exists ({len(l_text.split())} words).",
            why_it_matters="You give AI models a curated map of your best content. Early-mover signal.",
            impact=1, effort=1,
        ))
    else:
        findings.append(Finding(
            id="llms_missing", title="No llms.txt file", status="warn",
            evidence=f"{root}/llms.txt returned {l_status or 'no response'}.",
            why_it_matters=(
                "llms.txt is an emerging standard (adopted by Anthropic, Stripe, Cloudflare) that "
                "hands AI models a plain-English index of your key pages. Cost to add is near zero."
            ),
            fix="Create llms.txt at your site root. A starter, fill in the brackets:",
            fix_code=_llms_fix(root),
            impact=1, effort=1,
        ))

    # --- sitemap -----------------------------------------------------------
    has_sitemap_directive = "sitemap:" in robots_text.lower()
    s_status, _ = _fetch_text(urljoin(root + "/", "sitemap.xml"))
    if has_sitemap_directive or s_status == 200:
        findings.append(Finding(
            id="sitemap_ok", title="Sitemap is discoverable", status="pass",
            evidence="Found a sitemap (via robots.txt directive or /sitemap.xml).",
            why_it_matters="Crawlers can find all your pages, not just the ones they stumble on.",
            impact=1, effort=1,
        ))
    else:
        findings.append(Finding(
            id="sitemap_missing", title="No sitemap found", status="warn",
            evidence=f"No Sitemap: line in robots.txt and {root}/sitemap.xml returned {s_status or 'nothing'}.",
            why_it_matters="Without a sitemap, deeper pages may never be crawled or cited.",
            fix="Generate sitemap.xml and reference it in robots.txt: `Sitemap: " + root + "/sitemap.xml`",
            impact=1, effort=1,
        ))

    score = _score(findings)
    return CheckResult(
        key="accessibility", label="Machine Accessibility", score=score, weight=25,
        findings=findings,
        summary="Can AI engines reach, read, and identify this business?",
    )


def _schema_finding(home: Page, root: str) -> Finding:
    org = None
    types_found: set[str] = set()
    if home.soup:
        for tag in home.soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = tag.string if tag.string is not None else tag.get_text()
            try:
                data = json.loads(raw or "{}")
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            candidates = data if isinstance(data, list) else [data]
            nodes = []
            for candidate in candidates:
                if isinstance(candidate, dict) and isinstance(candidate.get("@graph"), list):
                    nodes.extend(candidate["@graph"])
                nodes.append(candidate)
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                t = node.get("@type", "")
                t = t if isinstance(t, str) else ",".join(t) if isinstance(t, list) else ""
                types_found.add(t)
                if any(x in t for x in ("Organization", "LocalBusiness")):
                    org = node
    if org:
        missing = [k for k in ("name", "description", "url", "sameAs") if not org.get(k)]
        if missing:
            return Finding(
                id="schema_thin", title="Organization schema exists but is thin", status="warn",
                evidence=f"Found {org.get('@type')} schema, but it's missing: {', '.join(missing)}.",
                why_it_matters=(
                    "AI engines use structured data to know who you are and what you're known for. "
                    "A name-and-URL stub isn't enough to build an entity around you. `sameAs` "
                    "(links to your LinkedIn, socials, listings) is how they connect the dots."
                ),
                fix="Complete your Organization schema. Example:",
                fix_code=_org_schema(root),
                impact=2, effort=1,
            )
        return Finding(
            id="schema_ok", title="Complete Organization schema found", status="pass",
            evidence=f"{org.get('@type')} schema present with name, description, url and sameAs.",
            why_it_matters="AI engines can clearly identify your business as an entity.",
            impact=2, effort=1,
        )
    return Finding(
        id="schema_missing", title="No Organization schema", status="fail",
        evidence=(
            "No Organization or LocalBusiness JSON-LD found on the homepage"
            + (f" (schema types present: {', '.join(sorted(t for t in types_found if t))})." if types_found else ".")
        ),
        why_it_matters=(
            "Without structured identity data, AI engines have to guess who you are from prose. "
            "Businesses with clear Organization schema are far easier to attribute and recommend."
        ),
        fix="Add Organization (or LocalBusiness) JSON-LD to your homepage <head>:",
        fix_code=_org_schema(root),
        impact=2, effort=1,
    )


def _score(findings: list[Finding]) -> float:
    weights = {"fail": 0.0, "warn": 0.5, "pass": 1.0, "info": 1.0}
    # Weight each finding by its own impact so a blocked-crawler fail hurts more.
    total = sum(f.impact for f in findings)
    got = sum(weights[f.status] * f.impact for f in findings)
    return round(got / total, 3) if total else 0.0


def _robots_fix(root: str) -> str:
    lines = ["User-agent: GPTBot", "Allow: /", "", "User-agent: OAI-SearchBot", "Allow: /",
             "", "User-agent: ChatGPT-User", "Allow: /", "", "User-agent: ClaudeBot", "Allow: /",
             "", "User-agent: Claude-SearchBot", "Allow: /", "", "User-agent: PerplexityBot",
             "Allow: /", "", "User-agent: Google-Extended", "Allow: /", "",
             f"Sitemap: {root}/sitemap.xml"]
    return "\n".join(lines)


def _llms_fix(root: str) -> str:
    return (
        "# [Business Name]\n\n"
        "> [One sentence: what you do and who you serve.]\n\n"
        "## Key pages\n"
        f"- [About]({root}/about): who we are\n"
        f"- [Services]({root}/services): what we offer\n"
        f"- [Contact]({root}/contact): how to reach us\n"
    )


def _org_schema(root: str) -> str:
    return (
        '<script type="application/ld+json">\n'
        "{\n"
        '  "@context": "https://schema.org",\n'
        '  "@type": "Organization",\n'
        '  "name": "[Business Name]",\n'
        '  "url": "' + root + '",\n'
        '  "description": "[One clear sentence about what you do and for whom]",\n'
        '  "sameAs": [\n'
        '    "https://www.linkedin.com/company/[you]",\n'
        '    "https://www.instagram.com/[you]"\n'
        "  ]\n"
        "}\n"
        "</script>"
    )
