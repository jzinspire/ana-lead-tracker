"""
Ana Lead Tracker — Real-data enrichment for prospect scoring.

This module turns each candidate business into a fact sheet of observable signals
so Claude has actual evidence to score against, instead of inferring from the
business name alone.

Two enrichment paths:
- Website signals: fetch homepage HTML, parse for tech / bilingual / urgency cues.
- Review signals: mine the latest Google reviews for complaint patterns,
  Spanish-language usage, and review velocity.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# WEBSITE SIGNAL DETECTION
# ---------------------------------------------------------------------------

# Known live-chat widget script signatures (case-insensitive substring match)
CHAT_WIDGET_SIGNATURES = [
    "intercom", "drift.com", "tawk.to", "tidio", "crisp.chat",
    "zopim", "zendesk.com/embeddable", "livechatinc", "olark",
    "smartsupp", "freshchat", "hubspot.com/messages",
]

# Online booking / scheduling system signatures
BOOKING_SIGNATURES = [
    "calendly", "acuityscheduling", "squareup.com/appointments",
    "schedulicity", "setmore", "appointy", "booksy", "vagaro",
    "mindbodyonline", "housecallpro", "servicetitan", "jobber",
]

# Modern JS framework / static-site-generator signatures
MODERN_FRAMEWORK_SIGNATURES = [
    "_next/", "react", "vue.runtime", "angular", "svelte",
    "gatsby", "nuxt", "/_nuxt/", "astro",
]

# Spanish-language link patterns
SPANISH_LINK_PATTERNS = [
    re.compile(r'/es/', re.I),
    re.compile(r'/es-', re.I),
    re.compile(r'/spanish/', re.I),
    re.compile(r'lang=es', re.I),
    re.compile(r'language=es', re.I),
]

SPANISH_TEXT_KEYWORDS = [
    "español", "espanol", "hablamos español", "se habla español",
    "habla español", "en español",
]

# Family-business naming patterns
FAMILY_NAME_PATTERNS = [
    re.compile(r'\b&\s*sons?\b', re.I),
    re.compile(r'\b&\s*daughters?\b', re.I),
    re.compile(r'\b&\s*family\b', re.I),
    re.compile(r'\bfamily\s*owned\b', re.I),
    re.compile(r'\bfamily[-\s]*operated\b', re.I),
    re.compile(r'\bsince\s*\d{4}\b', re.I),  # "Since 1985"
    re.compile(r'\b\d+\s*(years?|generations?)\s+(in business|of service|family)\b', re.I),
]

# Careers / hiring signals (urgency proxy)
HIRING_LINK_KEYWORDS = ["career", "careers", "job", "jobs", "hiring", "we're hiring", "join our team", "join us"]


def fetch_website(url: str, timeout: int = 8) -> tuple[str | None, int | None]:
    """Fetch a website's homepage HTML.

    Returns (html, status_code). Returns (None, None) on failure — never raises.
    Keeps timeouts short so a slow site doesn't block the whole research run.
    """
    if not url:
        return None, None

    # Normalize URL — Apify often gives bare hostnames
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        if resp.status_code == 200 and resp.text:
            return resp.text[:500_000], resp.status_code  # cap at 500KB
        return None, resp.status_code
    except Exception:
        return None, None


def parse_website_signals(url: str, html: str | None) -> dict[str, Any]:
    """Extract observable signals from a website's homepage HTML.

    Returns a dict of booleans + evidence strings. Used to feed Claude
    real data instead of letting it guess.
    """
    signals: dict[str, Any] = {
        "url": url,
        "fetched": html is not None,
        "has_https": bool(url and url.startswith("https://")),
        "has_spanish_version": False,
        "has_online_booking": False,
        "has_chat_widget": False,
        "has_mobile_viewport": False,
        "has_modern_framework": False,
        "has_careers_page": False,
        "family_business_signal": False,
        "booking_provider": None,
        "chat_provider": None,
        "framework_hint": None,
        "spanish_evidence": [],
        "family_evidence": [],
        "page_title": None,
        "copyright_year": None,
    }

    if not html:
        return signals

    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text(" ", strip=True).lower()
    raw_html_lower = html.lower()

    # Page title
    if soup.title and soup.title.string:
        signals["page_title"] = soup.title.string.strip()[:200]

    # Mobile viewport
    viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    signals["has_mobile_viewport"] = viewport_tag is not None

    # Chat widget detection
    for sig in CHAT_WIDGET_SIGNATURES:
        if sig in raw_html_lower:
            signals["has_chat_widget"] = True
            signals["chat_provider"] = sig
            break

    # Booking system detection
    for sig in BOOKING_SIGNATURES:
        if sig in raw_html_lower:
            signals["has_online_booking"] = True
            signals["booking_provider"] = sig
            break

    # Also catch generic "book online" / "schedule appointment" links if no
    # specific provider matched
    if not signals["has_online_booking"]:
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").lower()
            text = (a.get_text() or "").lower()
            if any(
                kw in href or kw in text
                for kw in ["book online", "book now", "schedule appointment", "request appointment", "book a"]
            ):
                signals["has_online_booking"] = True
                signals["booking_provider"] = "generic"
                break

    # Modern framework detection
    for sig in MODERN_FRAMEWORK_SIGNATURES:
        if sig in raw_html_lower:
            signals["has_modern_framework"] = True
            signals["framework_hint"] = sig
            break

    # Spanish version detection — multiple signals
    spanish_evidence = []

    # hreflang
    for link in soup.find_all("link", attrs={"hreflang": re.compile(r"^es", re.I)}):
        spanish_evidence.append(f'hreflang="{link.get("hreflang")}"')
        break

    # Link patterns
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = (a.get_text() or "").strip()
        for pattern in SPANISH_LINK_PATTERNS:
            if pattern.search(href):
                spanish_evidence.append(f"link: {href}")
                break
        # Visible "Español" link text
        if any(kw in text.lower() for kw in ["español", "espanol", "spanish"]):
            spanish_evidence.append(f"link text: {text[:30]}")

    # Inline Spanish marketing text
    for kw in SPANISH_TEXT_KEYWORDS:
        if kw in text_content:
            spanish_evidence.append(f'page text mentions "{kw}"')
            break

    signals["has_spanish_version"] = bool(spanish_evidence)
    signals["spanish_evidence"] = spanish_evidence[:3]  # cap

    # Family business signals (homepage + footer text)
    family_evidence = []
    full_text_for_family = (signals.get("page_title") or "") + " " + text_content
    for pattern in FAMILY_NAME_PATTERNS:
        m = pattern.search(full_text_for_family)
        if m:
            family_evidence.append(m.group(0).strip())
    signals["family_business_signal"] = bool(family_evidence)
    signals["family_evidence"] = family_evidence[:3]

    # Careers / hiring page
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").lower()
        text = (a.get_text() or "").lower()
        if any(kw in href or kw in text for kw in HIRING_LINK_KEYWORDS):
            signals["has_careers_page"] = True
            break

    # Copyright year — proxy for "site is actively maintained"
    copyright_match = re.search(r"©\s*(\d{4})", text_content)
    if copyright_match:
        signals["copyright_year"] = int(copyright_match.group(1))

    # Business association badges — adds real credibility signals.
    # See parse_association_signals() for what we look for.
    signals.update(parse_association_signals(soup, html, url, text_content))

    return signals


# ---------------------------------------------------------------------------
# BUSINESS ASSOCIATION DETECTION (Phase 7)
# ---------------------------------------------------------------------------
# We look for membership badges/logos/text mentions on the business's homepage.
# These are strong real-data signals:
#   - BBB Accreditation → trust + mature business → +Ease of Closing
#   - Hispanic Chamber membership → ACTIVELY serves Spanish market → +Bilingual
#   - NFIB → "I'm an independent SMB owner" → +Ease of Closing
#   - Industry associations (ACCA, PHCC, NAIFA, NPMA, SEIA) → industry engagement
#
# Detection uses TWO methods per association to reduce false positives:
#   - Strong: image alt/src OR link href to the association's domain
#   - Weak: explicit phrase in body text
# We require at least one strong signal to flag membership.


# BBB
BBB_DOMAINS = ["bbb.org", "betterbusinessbureau"]
BBB_PHRASES = ["bbb accredited", "accredited business", "better business bureau"]

# Hispanic Chambers (Phoenix Valley specific)
HISPANIC_CHAMBER_DOMAINS = [
    "azhcc.com",          # Arizona Hispanic Chamber
    "phoenixhcc.com",     # Phoenix Hispanic Chamber
    "phoenixhispanicchamber",
    "evhcc.com",          # East Valley Hispanic Chamber
    "westvalleyhcc",
]
HISPANIC_CHAMBER_PHRASES = [
    "hispanic chamber",
    "cámara hispana",
    "camara hispana",
    "cámara de comercio hispana",
    "azhcc",
]

# Generic Chamber of Commerce (any Phoenix Valley chamber)
CHAMBER_DOMAINS = [
    "phoenixchamber.com",
    "mesachamber.org",
    "scottsdalechamber.com",
    "tempechamber.org",
    "chandlerchamber.com",
    "gilbertaz.gov/chamber",
    "glendaleazchamber",
    "peoriachamber.org",
    "surpriseregionalchamber",
    "avondalechamber",
    "goodyearchamber",
    "buckeyevalleychamber",
    "chamberofcommerce.com",
]
CHAMBER_PHRASES = ["chamber of commerce member", "member of the chamber"]

# NFIB
NFIB_DOMAINS = ["nfib.com", "nfib.org"]
NFIB_PHRASES = ["nfib member", "national federation of independent business"]

# Industry-specific associations
INDUSTRY_ASSOCIATIONS = {
    "ACCA": {  # Air Conditioning Contractors of America (HVAC)
        "domains": ["acca.org"],
        "phrases": ["acca member", "air conditioning contractors of america"],
    },
    "PHCC": {  # Plumbing-Heating-Cooling Contractors
        "domains": ["phccweb.org"],
        "phrases": ["phcc member", "plumbing-heating-cooling contractors"],
    },
    "NAIFA": {  # National Association of Insurance and Financial Advisors
        "domains": ["naifa.org"],
        "phrases": ["naifa member", "national association of insurance and financial"],
    },
    "NPMA": {  # National Pest Management Association
        "domains": ["npmapestworld.org", "npma.org"],
        "phrases": ["npma member", "national pest management"],
    },
    "SEIA": {  # Solar Energy Industries Association
        "domains": ["seia.org"],
        "phrases": ["seia member", "solar energy industries association"],
    },
    "Trusted Choice": {  # Independent insurance agent network
        "domains": ["trustedchoice.com"],
        "phrases": ["trusted choice", "independent insurance agent"],
    },
    "AAA": {  # Auto service / restoration approvals
        "domains": ["aaa.com/approved", "aaaapproved"],
        "phrases": ["aaa approved auto repair"],
    },
}


def _domain_referenced(soup, html_lower: str, domains: list[str]) -> str | None:
    """Return the matching domain if any appears in image src, link href, or
    raw HTML. None otherwise."""
    for d in domains:
        if d in html_lower:
            return d
    return None


def _phrase_in_text(text_lower: str, phrases: list[str]) -> str | None:
    """Return the matching phrase if any appears in the page text. None otherwise."""
    for p in phrases:
        if p in text_lower:
            return p
    return None


def parse_association_signals(
    soup: BeautifulSoup, html: str | None, url: str, text_content: str
) -> dict[str, Any]:
    """Detect business-association memberships from the business's homepage.

    Strong evidence: domain reference (image src, link href, or anywhere
    in the raw HTML). Weak evidence: phrase in visible page text. We
    flag membership only when there's at least one strong OR a phrase
    paired with surrounding context. Stored as both booleans and a
    human-readable evidence list.
    """
    signals: dict[str, Any] = {
        "bbb_accredited": False,
        "hispanic_chamber_member": False,
        "chamber_member": False,
        "nfib_member": False,
        "industry_associations": [],
        "association_evidence": [],
    }

    if not html:
        return signals

    html_lower = html.lower()
    text_lower = text_content.lower() if text_content else ""

    # BBB
    bbb_domain = _domain_referenced(soup, html_lower, BBB_DOMAINS)
    bbb_phrase = _phrase_in_text(text_lower, BBB_PHRASES)
    if bbb_domain or bbb_phrase:
        signals["bbb_accredited"] = True
        if bbb_domain:
            signals["association_evidence"].append(f"BBB: domain reference ({bbb_domain})")
        elif bbb_phrase:
            signals["association_evidence"].append(f'BBB: text mentions "{bbb_phrase}"')

    # Hispanic Chamber (high-signal for Bilingual)
    hc_domain = _domain_referenced(soup, html_lower, HISPANIC_CHAMBER_DOMAINS)
    hc_phrase = _phrase_in_text(text_lower, HISPANIC_CHAMBER_PHRASES)
    if hc_domain or hc_phrase:
        signals["hispanic_chamber_member"] = True
        if hc_domain:
            signals["association_evidence"].append(f"Hispanic Chamber: domain reference ({hc_domain})")
        elif hc_phrase:
            signals["association_evidence"].append(f'Hispanic Chamber: text mentions "{hc_phrase}"')

    # Generic Chamber of Commerce
    ch_domain = _domain_referenced(soup, html_lower, CHAMBER_DOMAINS)
    ch_phrase = _phrase_in_text(text_lower, CHAMBER_PHRASES)
    if ch_domain or ch_phrase:
        signals["chamber_member"] = True
        if ch_domain:
            signals["association_evidence"].append(f"Chamber: domain reference ({ch_domain})")
        elif ch_phrase:
            signals["association_evidence"].append(f'Chamber: text mentions "{ch_phrase}"')

    # NFIB
    nfib_domain = _domain_referenced(soup, html_lower, NFIB_DOMAINS)
    nfib_phrase = _phrase_in_text(text_lower, NFIB_PHRASES)
    if nfib_domain or nfib_phrase:
        signals["nfib_member"] = True
        if nfib_domain:
            signals["association_evidence"].append(f"NFIB: domain reference ({nfib_domain})")
        elif nfib_phrase:
            signals["association_evidence"].append(f'NFIB: text mentions "{nfib_phrase}"')

    # Industry-specific associations
    for name, refs in INDUSTRY_ASSOCIATIONS.items():
        domain_hit = _domain_referenced(soup, html_lower, refs["domains"])
        phrase_hit = _phrase_in_text(text_lower, refs["phrases"])
        if domain_hit or phrase_hit:
            signals["industry_associations"].append(name)
            if domain_hit:
                signals["association_evidence"].append(f"{name}: domain reference ({domain_hit})")
            elif phrase_hit:
                signals["association_evidence"].append(f'{name}: text mentions "{phrase_hit}"')

    return signals


# ---------------------------------------------------------------------------
# REVIEW MINING
# ---------------------------------------------------------------------------

# Phrases customers use when describing missed-call pain
MISSED_CALL_COMPLAINT_PATTERNS = [
    re.compile(r"couldn'?t\s+reach", re.I),
    re.compile(r"could\s+not\s+reach", re.I),
    re.compile(r"no\s+answer", re.I),
    re.compile(r"didn'?t\s+answer", re.I),
    re.compile(r"never\s+(?:called|got)\s+back", re.I),
    re.compile(r"didn'?t\s+call\s+back", re.I),
    re.compile(r"hard\s+to\s+reach", re.I),
    re.compile(r"voicemail", re.I),
    re.compile(r"no\s+one\s+picks?\s+up", re.I),
    re.compile(r"phone\s+goes?\s+(?:straight\s+)?to\s+voicemail", re.I),
    re.compile(r"can'?t\s+get\s+a?\s*hold\s+of", re.I),
    re.compile(r"answering\s+service", re.I),
]

# Characters / words that are strong Spanish-language indicators
SPANISH_CHAR_PATTERN = re.compile(r"[ñáéíóúü¿¡]", re.I)
SPANISH_WORDS = {
    "el", "la", "los", "las", "que", "para", "muy", "bueno", "buena",
    "excelente", "servicio", "gracias", "recomiendo", "trabajo", "todo",
    "todos", "casa", "ellos", "siempre", "nunca", "tambien", "también",
    "fueron", "estuvieron", "muy bien", "muy buena", "lo recomiendo",
}


def _is_spanish_review(text: str) -> bool:
    """Heuristic: a review is Spanish if it contains Spanish-only characters
    OR has 3+ Spanish stopwords in a short text."""
    if not text:
        return False
    if SPANISH_CHAR_PATTERN.search(text):
        return True
    words = set(re.findall(r"\b[a-záéíóúñ]+\b", text.lower()))
    return len(words & SPANISH_WORDS) >= 3


def parse_review_signals(apify_item: dict[str, Any]) -> dict[str, Any]:
    """Mine the Apify Google Maps `reviews` array for complaint patterns,
    Spanish-language usage, and review velocity.

    Apify's `drobnikj/crawler-google-places` returns reviews under the
    `reviews` key when `maxReviews > 0`. Each review has `text`,
    `publishedAtDate`, `stars`, etc.
    """
    reviews = apify_item.get("reviews") or []
    total_count = apify_item.get("reviewsCount") or apify_item.get("reviewsTotalCount") or 0
    avg_rating = apify_item.get("totalScore") or apify_item.get("averageRating")

    signals: dict[str, Any] = {
        "total_review_count": total_count,
        "avg_rating": avg_rating,
        "reviews_sampled": len(reviews),
        "spanish_review_count": 0,
        "spanish_review_pct": 0.0,
        "missed_call_complaint_count": 0,
        "missed_call_complaint_quotes": [],
        "recent_review_count_90d": 0,
        "review_velocity_signal": None,
    }

    if not reviews:
        return signals

    now = datetime.utcnow()
    cutoff_90d = now - timedelta(days=90)
    cutoff_365d = now - timedelta(days=365)

    spanish_count = 0
    complaint_count = 0
    complaint_quotes: list[str] = []
    recent_count = 0
    older_count = 0

    for r in reviews:
        text = (r.get("text") or "").strip()
        if not text:
            continue

        # Spanish detection
        if _is_spanish_review(text):
            spanish_count += 1

        # Missed-call complaint detection
        for pattern in MISSED_CALL_COMPLAINT_PATTERNS:
            m = pattern.search(text)
            if m:
                complaint_count += 1
                if len(complaint_quotes) < 3:
                    # Grab a short surrounding snippet
                    start = max(0, m.start() - 30)
                    end = min(len(text), m.end() + 60)
                    snippet = text[start:end].strip()
                    complaint_quotes.append(snippet)
                break  # only count each review once

        # Date parsing for velocity
        date_str = r.get("publishedAtDate") or r.get("publishAt")
        if date_str:
            try:
                # Handle both ISO format and "X months ago" style
                if "T" in str(date_str):
                    review_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00")).replace(tzinfo=None)
                    if review_date >= cutoff_90d:
                        recent_count += 1
                    elif review_date >= cutoff_365d:
                        older_count += 1
            except Exception:
                pass

    signals["spanish_review_count"] = spanish_count
    signals["spanish_review_pct"] = round(spanish_count / len(reviews) * 100, 1) if reviews else 0.0
    signals["missed_call_complaint_count"] = complaint_count
    signals["missed_call_complaint_quotes"] = complaint_quotes
    signals["recent_review_count_90d"] = recent_count

    # Velocity signal: more recent reviews than older = growing
    if recent_count > 0 and older_count > 0:
        ratio = recent_count / older_count
        if ratio >= 1.5:
            signals["review_velocity_signal"] = "accelerating"
        elif ratio <= 0.5:
            signals["review_velocity_signal"] = "slowing"
        else:
            signals["review_velocity_signal"] = "steady"

    return signals


# ---------------------------------------------------------------------------
# COMBINED ENRICHMENT
# ---------------------------------------------------------------------------

def enrich_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Run all enrichment passes on a candidate. Mutates and returns it.

    Adds these keys:
      - website_signals: dict
      - review_signals: dict
      - review_count: int
    """
    # Website enrichment
    website_url = candidate.get("website") or ""
    html, status = fetch_website(website_url) if website_url else (None, None)
    candidate["website_signals"] = parse_website_signals(website_url, html)
    candidate["website_signals"]["http_status"] = status

    # Review enrichment — needs the raw Apify item
    raw = candidate.get("research_data")
    apify_item: dict[str, Any] = {}
    if raw:
        try:
            apify_item = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            apify_item = {}

    candidate["review_signals"] = parse_review_signals(apify_item)
    candidate["review_count"] = candidate["review_signals"]["total_review_count"]

    return candidate


def signals_to_evidence_brief(candidate: dict[str, Any]) -> str:
    """Render a compact human-readable fact sheet from enrichment signals.

    This is what gets sent to Claude in the scoring prompt — it's the
    "real data" Claude will cite when scoring each criterion.
    """
    ws = candidate.get("website_signals") or {}
    rs = candidate.get("review_signals") or {}

    lines = [f"## {candidate.get('name', 'Unknown')} — {candidate.get('industry', 'Unknown industry')} in {candidate.get('city', 'Unknown city')}"]

    # Core facts
    lines.append(f"- Website: {candidate.get('website') or '(none)'}")
    if ws.get("page_title"):
        lines.append(f"- Page title: {ws['page_title']}")
    lines.append(f"- Phone: {candidate.get('phone') or '(none)'}")

    # Review facts
    lines.append("")
    lines.append("**Google reviews:**")
    lines.append(f"- Total review count: {rs.get('total_review_count', 'unknown')}")
    lines.append(f"- Avg rating: {rs.get('avg_rating', 'unknown')}")
    lines.append(f"- Reviews sampled: {rs.get('reviews_sampled', 0)}")
    if rs.get("recent_review_count_90d"):
        lines.append(f"- Reviews in last 90 days: {rs['recent_review_count_90d']}")
    if rs.get("review_velocity_signal"):
        lines.append(f"- Review velocity: {rs['review_velocity_signal']}")
    if rs.get("spanish_review_count"):
        lines.append(f"- Spanish-language reviews: {rs['spanish_review_count']} ({rs.get('spanish_review_pct', 0)}% of sample)")
    if rs.get("missed_call_complaint_count"):
        lines.append(f"- Missed-call complaints found in reviews: {rs['missed_call_complaint_count']}")
        for q in rs.get("missed_call_complaint_quotes", []):
            lines.append(f'  - "{q}"')

    # Website signals
    lines.append("")
    lines.append("**Website signals:**")
    lines.append(f"- Site fetched: {'yes' if ws.get('fetched') else 'no (could not reach)'}")
    if ws.get("fetched"):
        lines.append(f"- HTTPS: {'yes' if ws.get('has_https') else 'no'}")
        lines.append(f"- Mobile-responsive viewport: {'yes' if ws.get('has_mobile_viewport') else 'no'}")
        lines.append(f"- Online booking detected: {'yes (' + (ws.get('booking_provider') or '') + ')' if ws.get('has_online_booking') else 'no'}")
        lines.append(f"- Live chat widget detected: {'yes (' + (ws.get('chat_provider') or '') + ')' if ws.get('has_chat_widget') else 'no'}")
        lines.append(f"- Modern JS framework: {'yes (' + (ws.get('framework_hint') or '') + ')' if ws.get('has_modern_framework') else 'no'}")
        lines.append(f"- Spanish version on site: {'yes' if ws.get('has_spanish_version') else 'no'}")
        if ws.get("spanish_evidence"):
            for e in ws["spanish_evidence"]:
                lines.append(f"  - {e}")
        lines.append(f"- Family-business signals on site: {'yes' if ws.get('family_business_signal') else 'no'}")
        if ws.get("family_evidence"):
            for e in ws["family_evidence"]:
                lines.append(f'  - "{e}"')
        lines.append(f"- Careers / hiring page: {'yes' if ws.get('has_careers_page') else 'no'}")
        if ws.get("copyright_year"):
            lines.append(f"- Footer copyright year: {ws['copyright_year']}")

    # Business association memberships — added in Phase 7. These are
    # high-trust signals that meaningfully change scoring.
    if ws.get("fetched"):
        associations = []
        if ws.get("bbb_accredited"):
            associations.append("BBB Accredited")
        if ws.get("hispanic_chamber_member"):
            associations.append("Hispanic Chamber member (STRONG bilingual signal)")
        if ws.get("chamber_member"):
            associations.append("Chamber of Commerce member")
        if ws.get("nfib_member"):
            associations.append("NFIB member (independent SMB)")
        for ia in ws.get("industry_associations") or []:
            associations.append(f"{ia} member (industry association)")

        if associations:
            lines.append("")
            lines.append("**Business associations / credibility badges:**")
            for a in associations:
                lines.append(f"- {a}")
            for e in (ws.get("association_evidence") or [])[:5]:
                lines.append(f"  - evidence: {e}")

    return "\n".join(lines)
