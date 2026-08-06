"""
fetch.py — retrieve a site's pages the way an AI crawler would see them.

Key idea: AI crawlers (GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot) do NOT
run JavaScript. They read the raw HTML the server returns. So we fetch raw HTML
with a crawler-like user agent and measure how much *readable text* actually
exists before any JS runs. A site that renders its content client-side looks
like an empty shell to these bots — a silent, invisible-to-AI failure that
Google (which does render JS) hides from the owner.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# A realistic browser UA — bot UAs get 403'd by Cloudflare/WAF-protected sites.
CRAWLER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TIMEOUT = 20


def http_get(url: str):
    headers = {"User-Agent": CRAWLER_UA, "Accept-Language": "en-US,en;q=0.9"}
    try:
        return requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    except requests.exceptions.SSLError:
        return requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False)


@dataclass
class Page:
    url: str
    status: int
    html: str = ""
    error: str | None = None

    # Derived
    soup: BeautifulSoup | None = None
    visible_text: str = ""
    word_count: int = 0
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    is_js_shell: bool = False
    js_shell_reason: str = ""


def _clean_text(soup: BeautifulSoup) -> str:
    # Remove non-content nodes before measuring readable text.
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _detect_js_shell(html: str, visible_text: str, word_count: int) -> tuple[bool, str]:
    """Heuristic: is this page an empty shell that only fills in via JS?"""
    lowered = html.lower()
    root_markers = ('id="root"', "id='root'", 'id="__next"', 'id="app"', "id='app'", "ng-app")
    has_spa_root = any(m in lowered for m in root_markers)
    heavy_scripts = lowered.count("<script") >= 5

    if word_count < 120 and (has_spa_root or heavy_scripts):
        return True, (
            f"Only {word_count} words of text are present in the raw HTML, and the page "
            f"uses a client-side JS framework container. AI crawlers do not run JavaScript, "
            f"so they likely see a near-empty page."
        )
    if word_count < 60:
        return True, (
            f"Only {word_count} words of readable text in the raw HTML — too thin for an AI "
            f"engine to understand or cite what this business does."
        )
    return False, ""


def fetch_page(url: str) -> Page:
    try:
        resp = http_get(url)
    except requests.RequestException as e:
        return Page(url=url, status=0, error=str(e))

    page = Page(url=str(resp.url), status=resp.status_code, html=resp.text or "")
    if resp.status_code >= 400 or not page.html:
        return page

    soup = BeautifulSoup(page.html, "lxml")
    page.soup = soup
    page.title = (soup.title.string or "").strip() if soup.title else ""
    md = soup.find("meta", attrs={"name": "description"})
    page.meta_description = (md.get("content", "").strip() if md else "")
    h1 = soup.find("h1")
    page.h1 = h1.get_text(strip=True) if h1 else ""

    page.visible_text = _clean_text(BeautifulSoup(page.html, "lxml"))
    page.word_count = len(page.visible_text.split())
    page.is_js_shell, page.js_shell_reason = _detect_js_shell(
        page.html, page.visible_text, page.word_count
    )
    return page


def discover_key_pages(home: Page, base_url: str, limit: int = 4) -> list[str]:
    """Find a few high-value internal pages (about / services / products / pricing)."""
    if not home.soup:
        return []
    priority = ("about", "service", "product", "pricing", "solution", "menu", "contact")
    found: list[str] = []
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    for a in home.soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        full = urljoin(base_url, href)
        if urlparse(full).netloc != urlparse(root).netloc:
            continue
        path = urlparse(full).path.lower()
        if any(k in path for k in priority) and full not in found and full != home.url:
            found.append(full)
        if len(found) >= limit:
            break
    return found


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw
