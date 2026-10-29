"""Fetch a business homepage (and its contact page) and extract signals about its web presence."""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from leadfinder.models import Business, WebsiteSignals

USER_AGENT = "Mozilla/5.0 (compatible; lead-finder-agent/0.1; +https://github.com/lead-finder-agent)"

BOOKING_PATTERNS = re.compile(
    r"calendly|booksy|fresha|setmore|acuityscheduling|simplybook|treatwell|opentable|"
    r"booking\.com/hotel|doctolib|book (an )?appointment|book now|online booking|κράτηση|ραντεβού",
    re.I,
)
CHAT_PATTERNS = re.compile(
    r"tawk\.to|intercom|crisp\.chat|drift\.com|livechat|zendesk|tidio|hubspot|messenger|wa\.me|whatsapp",
    re.I,
)
ANALYTICS_PATTERNS = re.compile(
    r"googletagmanager\.com|google-analytics\.com|gtag\(|plausible\.io|matomo|clarity\.ms|hotjar", re.I
)
AD_PIXEL_PATTERNS = re.compile(
    r"connect\.facebook\.net|fbq\(|snap\.licdn\.com|tiktok\.com/i18n/pixel|ads-twitter", re.I
)
CMS_SIGNATURES = [
    ("WordPress", re.compile(r"wp-content|wp-includes", re.I)),
    ("Wix", re.compile(r"wixstatic\.com|_wix", re.I)),
    ("Squarespace", re.compile(r"squarespace\.com|static1\.squarespace", re.I)),
    ("Shopify", re.compile(r"cdn\.shopify\.com", re.I)),
    ("Joomla", re.compile(r"/media/jui/|joomla", re.I)),
    ("Webflow", re.compile(r"webflow\.(com|io)", re.I)),
    ("GoDaddy", re.compile(r"img1\.wsimg\.com", re.I)),
]
COPYRIGHT_RE = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})", re.I)
CONTACT_LINK_RE = re.compile(r"contact|kontakt|επικοινων|contatti|contacto", re.I)
SOCIAL_DOMAINS = ("facebook.com", "instagram.com", "linkedin.com", "tiktok.com", "youtube.com", "x.com", "twitter.com")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IGNORED_EMAIL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def _has_contact_form(soup: BeautifulSoup) -> bool:
    return any(
        f.find(["textarea", "input"], attrs={"type": lambda t: t in (None, "text", "email", "tel")})
        for f in soup.find_all("form")
    )


def _emails(html: str, links: list[str]) -> set[str]:
    found = {m for m in EMAIL_RE.findall(html) if not m.lower().endswith(_IGNORED_EMAIL_SUFFIXES)}
    found |= {l[7:].split("?")[0] for l in links if l.lower().startswith("mailto:")}
    return found


def find_contact_page(soup: BeautifulSoup, base_url: str) -> str:
    """Return the absolute URL of a same-site contact page link, if any."""
    host = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        if CONTACT_LINK_RE.search(a["href"]) or CONTACT_LINK_RE.search(a.get_text(" ", strip=True)):
            url = urljoin(base_url, a["href"])
            if urlparse(url).netloc == host and url.rstrip("/") != base_url.rstrip("/"):
                return url
    return ""


def extract_signals(html: str, final_url: str) -> WebsiteSignals:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = (desc_tag.get("content") or "").strip() if desc_tag else ""

    links = [a.get("href", "") for a in soup.find_all("a")]
    social = sorted({l.split("?")[0] for l in links if any(d in l for d in SOCIAL_DOMAINS)})
    cms = next((name for name, rx in CMS_SIGNATURES if rx.search(html)), "")

    this_year = dt.date.today().year
    years = [int(y) for y in COPYRIGHT_RE.findall(html) if 1995 <= int(y) <= this_year]
    contact_page = find_contact_page(soup, final_url)
    has_h1 = soup.find("h1") is not None
    has_viewport = soup.find("meta", attrs={"name": "viewport"}) is not None
    has_form = _has_contact_form(soup)

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()

    return WebsiteSignals(
        reachable=True,
        final_url=final_url,
        https=final_url.lower().startswith("https://"),
        mobile_friendly=has_viewport,
        has_contact_form=has_form,
        has_booking=bool(BOOKING_PATTERNS.search(html)),
        has_chat_widget=bool(CHAT_PATTERNS.search(html)),
        has_analytics=bool(ANALYTICS_PATTERNS.search(html)),
        has_ad_pixel=bool(AD_PIXEL_PATTERNS.search(html)),
        cms=cms,
        copyright_year=max(years) if years else None,
        has_h1=has_h1,
        contact_page=contact_page,
        social_links=social[:6],
        emails=sorted(_emails(html, links))[:5],
        title=title[:200],
        description=description[:300],
        text_excerpt=text[:1500],
    )


async def _check_contact_page(client: httpx.AsyncClient, signals: WebsiteSignals) -> None:
    """Many small sites keep the form/email on /contact. Merge what we find there."""
    try:
        resp = await client.get(
            signals.contact_page, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=10
        )
    except httpx.HTTPError:
        return
    if resp.status_code >= 400:
        return
    soup = BeautifulSoup(resp.text, "html.parser")
    signals.has_contact_form = signals.has_contact_form or _has_contact_form(soup)
    signals.has_booking = signals.has_booking or bool(BOOKING_PATTERNS.search(resp.text))
    links = [a.get("href", "") for a in soup.find_all("a")]
    signals.emails = sorted(set(signals.emails) | _emails(resp.text, links))[:5]


async def fetch_signals(client: httpx.AsyncClient, url: str) -> WebsiteSignals:
    start = time.perf_counter()
    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=12)
    except httpx.HTTPError as e:
        return WebsiteSignals(reachable=False, error=type(e).__name__)
    elapsed = int((time.perf_counter() - start) * 1000)
    if resp.status_code >= 400:
        return WebsiteSignals(
            reachable=False,
            status_code=resp.status_code,
            final_url=str(resp.url),
            response_ms=elapsed,
            error=f"HTTP {resp.status_code}",
        )
    signals = extract_signals(resp.text, str(resp.url))
    signals.status_code = resp.status_code
    signals.response_ms = elapsed
    if signals.contact_page and not (signals.has_contact_form and signals.emails):
        await _check_contact_page(client, signals)
    return signals


async def enrich_all(
    client: httpx.AsyncClient, businesses: list[Business], concurrency: int = 5
) -> list[WebsiteSignals | None]:
    """Fetch signals for every business that has a website (None for those without)."""
    sem = asyncio.Semaphore(concurrency)

    async def one(b: Business) -> WebsiteSignals | None:
        if not b.website:
            return None
        async with sem:
            return await fetch_signals(client, b.website)

    return await asyncio.gather(*(one(b) for b in businesses))
