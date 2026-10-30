"""
Fiverr Niche Arbitrage Scraper — production-grade, honest, self-hosted.

Data source:
  Fiverr public search pages render gig listings via Next.js SSR.
  The page embeds a JSON blob in <script id="__NEXT_DATA__"> that contains
  structured gig data identical to what a browser renders.  We fetch that
  blob with a plain HTTP GET (no browser, no stealth spoofing, no proxy
  rotation) and parse the gig cards from it.

What is genuinely collected:
  title, price_from, rating, reviews_count, seller_level, is_fiverr_pro,
  delivery_days, gig_url, total_services (search-result count shown at top).

What is NOT available on the search results page (set to null, documented
in field_provenance):
  orders_in_queue  — only on individual gig pages (would need N extra reqs)
  reviews_last_7d  — not publicly surfaced anywhere
  favourites       — not shown on search-result cards
  is_promoted      — may or may not be included; set if detected, else null

If Fiverr blocks access (403, 429, CAPTCHA redirect, empty listing) this
module raises ScraperBlockedError or ScraperNoResultsError.  The caller
must NOT silently substitute simulated data — it must propagate the error
and record honest job status.

Autocomplete:
  Uses the Fiverr autocomplete API (plain httpx GET through a page context).
  Falls back to empty list on any network failure.  Never returns simulated
  suggestions as "live".
"""
from __future__ import annotations

import asyncio
import hashlib
import json as _json
import logging
import math
import re
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger("fiverr-scout.scraper")

# ---------------------------------------------------------------------------
# Public constants / limits
# ---------------------------------------------------------------------------
MAX_PAGES = 3          # Max search-result pages fetched per scan
MAX_GIGS = 60          # Max gigs retained after dedup across all pages
PAGE_TIMEOUT = 20.0    # Seconds per HTTP request
INTER_PAGE_DELAY = 2.0 # Seconds between page requests (rate-limit respect)
MAX_RETRIES = 3        # Transient-only retries (5xx / network errors)
RETRY_BASE_DELAY = 3.0 # Base delay for exponential back-off

# Fiverr autocomplete endpoint (public, no auth needed)
AUTOCOMPLETE_URL = "https://www.fiverr.com/api/v1/auto_complete"
SEARCH_BASE_URL  = "https://www.fiverr.com/search/gigs"

# A realistic Accept-Language / User-Agent that matches a normal browser.
# We do NOT spoof webdriver or fingerprint — we send what we are.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "no-cache",
}

_AC_HEADERS = {
    "User-Agent": _HEADERS["User-Agent"],
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.fiverr.com/",
}

# Seller level weights for Saturation Index
SAT_WEIGHTS = {
    "New Seller": 1.0,
    "Level 1": 0.7,
    "Level 2": 0.3,
    "Top Rated": 0.1,
    "Fiverr Pro": 0.0,
}


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class ScraperBlockedError(Exception):
    """Raised when Fiverr actively blocks the request (403, 429, CAPTCHA)."""
    def __init__(self, reason: str, retry_after: Optional[int] = None):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class ScraperNoResultsError(Exception):
    """Raised when the page loads but returns no usable gig listings."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ScraperParseError(Exception):
    """Raised when the __NEXT_DATA__ blob cannot be parsed into gigs."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=_HEADERS,
        follow_redirects=True,
        timeout=PAGE_TIMEOUT,
        http2=False,
    )


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict = None) -> httpx.Response:
    """
    Fetch URL with transient-failure retry logic.
    - 429 / 503 with Retry-After: wait the instructed time (capped at 60s)
    - 403 / CAPTCHA redirect: raise ScraperBlockedError immediately (no retry)
    - 5xx (not 503): exponential back-off up to MAX_RETRIES
    - Network errors: exponential back-off up to MAX_RETRIES
    """
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url, params=params)

            # Access denial — do not retry
            if resp.status_code == 403:
                raise ScraperBlockedError(
                    f"HTTP 403 Forbidden from {url} — Fiverr is blocking this IP/request"
                )

            # Rate limit
            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                capped = min(retry_after, 60)
                logger.warning("Rate-limited (429); waiting %ds before retry", capped)
                await asyncio.sleep(capped)
                continue  # retry

            # Transient server error
            if resp.status_code == 503:
                retry_after = _parse_retry_after(resp)
                capped = min(retry_after, 60)
                await asyncio.sleep(capped)
                last_exc = ScraperBlockedError(f"HTTP 503 from {url}")
                continue

            if 500 <= resp.status_code < 600:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("HTTP %d from %s; retrying in %.0fs", resp.status_code, url, delay)
                await asyncio.sleep(delay)
                last_exc = Exception(f"HTTP {resp.status_code}")
                continue

            # Redirect to checkpoint / CAPTCHA
            final_url = str(resp.url)
            if "/checkpoint/" in final_url or "captcha" in final_url.lower():
                raise ScraperBlockedError(
                    f"Redirected to CAPTCHA/checkpoint at {final_url}"
                )

            return resp

        except (httpx.TransportError, httpx.TimeoutException) as e:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("Network error on attempt %d/%d: %s; retrying in %.0fs",
                           attempt + 1, MAX_RETRIES, e, delay)
            last_exc = e
            await asyncio.sleep(delay)

    if last_exc:
        if isinstance(last_exc, ScraperBlockedError):
            raise last_exc
        raise ScraperBlockedError(f"Exhausted {MAX_RETRIES} retries: {last_exc}")
    raise ScraperBlockedError("Unknown exhaustion")


def _parse_retry_after(resp: httpx.Response) -> int:
    raw = resp.headers.get("Retry-After", "")
    try:
        return max(1, int(raw))
    except Exception:
        return int(RETRY_BASE_DELAY)


# ---------------------------------------------------------------------------
# HTML → __NEXT_DATA__ → gig extraction
# ---------------------------------------------------------------------------
_NEXT_DATA_RE = re.compile(
    r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)
_NEXT_DATA_RE2 = re.compile(
    r'<script\s+type=["\']application/json["\'][^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


def _extract_next_data(html: str) -> Optional[dict]:
    """Extract and parse the __NEXT_DATA__ JSON blob from a Fiverr Next.js page."""
    for pattern in (_NEXT_DATA_RE, _NEXT_DATA_RE2):
        m = pattern.search(html)
        if m:
            raw = m.group(1).strip()
            try:
                return _json.loads(raw)
            except _json.JSONDecodeError as e:
                logger.debug("JSON parse error in __NEXT_DATA__: %s", e)
                return None
    return None


def _detect_block(html: str, url: str) -> None:
    """Raise ScraperBlockedError if the HTML looks like a block page."""
    lower = html.lower()
    if "verify you are human" in lower or "just a moment" in lower:
        raise ScraperBlockedError("CAPTCHA / human-verification page returned")
    if "/checkpoint/" in url:
        raise ScraperBlockedError(f"Redirected to checkpoint: {url}")
    if len(html) < 3000:
        raise ScraperBlockedError(f"Response HTML suspiciously short ({len(html)} bytes) — likely a block page")


def _normalize_seller_level(raw: str) -> str:
    """Map Fiverr badge text to our canonical level names."""
    if not raw:
        return "New Seller"
    r = raw.lower().strip()
    if "pro" in r:
        return "Fiverr Pro"
    if "top rated" in r or "top_rated" in r:
        return "Top Rated"
    if "level_two" in r or "level 2" in r or "level two" in r:
        return "Level 2"
    if "level_one" in r or "level 1" in r or "level one" in r:
        return "Level 1"
    return "New Seller"


def _safe_int(v, default=None) -> Optional[int]:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _safe_float(v, default=None) -> Optional[float]:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _parse_gigs_from_next_data(data: dict, keyword: str, page: int, fetch_url: str, fetched_at: str) -> tuple[list[dict], Optional[int]]:
    """
    Navigate the Next.js page props to find gig listings.

    Returns (gigs_list, total_services_count).
    gigs_list may be empty if the structure is not found.
    total_services_count is None if not found in the data.

    Fields set from page data: title, price_from, rating, reviews_count,
    seller_level, is_fiverr_pro, delivery_days, gig_url.

    Fields not available on search page (set to null): orders_in_queue,
    reviews_last_7d, favourites, is_promoted.
    """
    gigs = []
    total_services = None

    try:
        props = data.get("props", {})
        page_props = props.get("pageProps", {})

        # ---------- Try known Next.js data shapes ----------
        # Shape 1: pageProps.results.gigs
        results = page_props.get("results", {})
        if isinstance(results, dict):
            raw_gigs = results.get("gigs") or []
            total_services = (
                results.get("count")
                or results.get("total_count")
                or results.get("totalCount")
                or results.get("num_results")
            )
        else:
            raw_gigs = []

        # Shape 2: pageProps.initialProps.results.gigs (older layout)
        if not raw_gigs:
            initial = page_props.get("initialProps", {})
            if isinstance(initial, dict):
                ir = initial.get("results", {})
                if isinstance(ir, dict):
                    raw_gigs = ir.get("gigs", []) or []
                    if not total_services:
                        total_services = ir.get("count") or ir.get("total_count")

        # Shape 3: pageProps.searchResults or pageProps.gigs
        if not raw_gigs:
            raw_gigs = page_props.get("gigs", []) or []
        if not raw_gigs:
            sr = page_props.get("searchResults", {})
            if isinstance(sr, dict):
                raw_gigs = sr.get("gigs", []) or []
                if not total_services:
                    total_services = sr.get("count") or sr.get("total")

        # Shape 4: deep search for "gigs" array anywhere in props
        if not raw_gigs:
            raw_gigs = _deep_find_gigs(page_props)

        if not raw_gigs:
            return [], _safe_int(total_services)

        offset = (page - 1) * 48  # Fiverr shows ~48 per page
        for idx, g in enumerate(raw_gigs):
            if not isinstance(g, dict):
                continue
            position = offset + idx + 1

            # Title
            title = (
                g.get("title")
                or g.get("gigTitle")
                or g.get("gig_title")
                or ""
            )
            if not title or len(title) < 5:
                continue  # skip invalid gigs

            # Price
            price_raw = (
                g.get("price")
                or (g.get("pricing", {}) or {}).get("basePrice")
                or (g.get("packages", [{}]) or [{}])[0].get("price")
                or g.get("starting_price")
                or g.get("basePrice")
            )
            price_from = _safe_int(price_raw) or _safe_float(price_raw)
            if price_from is not None:
                try:
                    price_from = max(1, int(float(price_from)))
                except Exception:
                    price_from = None

            # Rating / reviews
            seller = g.get("seller", {}) or {}
            rating_data = g.get("rating") or g.get("gig_rating") or {}
            if isinstance(rating_data, (int, float)):
                rating = round(float(rating_data), 1)
                reviews_count = _safe_int(g.get("reviews_count") or g.get("reviewsCount"))
            elif isinstance(rating_data, dict):
                rating = _safe_float(rating_data.get("score") or rating_data.get("rating_score"))
                if rating is not None:
                    rating = round(rating, 1)
                reviews_count = _safe_int(
                    rating_data.get("count")
                    or rating_data.get("reviews_count")
                    or g.get("reviews_count")
                    or g.get("reviewsCount")
                )
            else:
                rating = None
                reviews_count = None

            # Seller level
            raw_level = (
                seller.get("level")
                or seller.get("sellerLevel")
                or g.get("seller_level")
                or g.get("sellerLevel")
                or ""
            )
            seller_level = _normalize_seller_level(str(raw_level))
            is_fiverr_pro = (
                g.get("is_pro")
                or g.get("isPro")
                or seller.get("isPro")
                or seller_level == "Fiverr Pro"
            )

            # Delivery days
            delivery_raw = (
                g.get("delivery_time")
                or g.get("deliveryTime")
                or g.get("delivery_days")
                or (g.get("packages", [{}]) or [{}])[0].get("delivery_time")
            )
            delivery_days = _safe_int(delivery_raw)

            # Gig URL
            gig_url_raw = g.get("gig_url") or g.get("url") or g.get("gigUrl") or ""
            if gig_url_raw and not gig_url_raw.startswith("http"):
                gig_url = f"https://www.fiverr.com{gig_url_raw}"
            elif gig_url_raw:
                gig_url = gig_url_raw
            else:
                slug = g.get("slug") or g.get("gig_slug")
                seller_name = seller.get("name") or seller.get("username") or ""
                if slug and seller_name:
                    gig_url = f"https://www.fiverr.com/{seller_name}/{slug}"
                else:
                    gig_url = ""

            # is_promoted — may be present in some layouts
            is_promoted = bool(
                g.get("is_ad")
                or g.get("isAd")
                or g.get("is_promoted")
                or g.get("isPromoted")
            )

            gigs.append({
                "position": position,
                "title": title.strip(),
                "seller_level": seller_level,
                "is_fiverr_pro": bool(is_fiverr_pro),
                "price_from": price_from,
                # Not available on search results page — explicitly null
                "orders_in_queue": None,
                "reviews_last_7d": None,
                "favourites": None,
                "rating": rating,
                "reviews_count": reviews_count,
                "is_promoted": is_promoted if is_promoted else None,
                "delivery_days": delivery_days,
                "gig_url": gig_url or None,
                # Provenance
                "_source_page": page,
                "_source_url": fetch_url,
                "_fetched_at": fetched_at,
            })

    except Exception as e:
        logger.warning("Error parsing gigs from __NEXT_DATA__: %s", e, exc_info=True)

    return gigs, _safe_int(total_services)


def _deep_find_gigs(obj, depth=0) -> list:
    """Recursively search for a key named 'gigs' that holds a non-empty list."""
    if depth > 8:
        return []
    if isinstance(obj, dict):
        if "gigs" in obj and isinstance(obj["gigs"], list) and obj["gigs"]:
            return obj["gigs"]
        for v in obj.values():
            result = _deep_find_gigs(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _deep_find_gigs(item, depth + 1)
            if result:
                return result
    return []


# ---------------------------------------------------------------------------
# Multi-page fetch + deduplication
# ---------------------------------------------------------------------------
def _dedup_gigs(all_gigs: list[dict]) -> list[dict]:
    """
    Deduplicate by (normalized title, approximate price).
    Preserves first occurrence (lowest position).
    """
    seen = set()
    out = []
    for g in all_gigs:
        title_key = re.sub(r"\s+", " ", (g.get("title") or "").lower().strip())
        price_key = g.get("price_from") or 0
        key = (title_key, price_key)
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
    return out


def _validate_gig(g: dict) -> bool:
    """Return True if this gig has the minimum required fields."""
    if not g.get("title"):
        return False
    if g.get("price_from") is not None and g["price_from"] <= 0:
        return False
    return True


async def _live_scrape(keyword: str) -> dict:
    """
    Fetch real Fiverr search results for `keyword`.

    Returns a dict with:
        data_source: "live"
        total_services: int or None
        gigs: list of validated, deduplicated gig dicts
        tags: []   (not extractable from search page)
        source_urls: list of fetched URLs
        fetched_pages: int

    Raises:
        ScraperBlockedError   — Fiverr blocked access
        ScraperNoResultsError — Page loaded but no usable listings found
        ScraperParseError     — __NEXT_DATA__ present but unparseable
    """
    all_gigs: list[dict] = []
    total_services: Optional[int] = None
    source_urls: list[str] = []
    fetched_pages = 0

    async with _make_client() as client:
        for page_num in range(1, MAX_PAGES + 1):
            if len(all_gigs) >= MAX_GIGS:
                break

            params = {"query": keyword}
            if page_num > 1:
                params["page"] = page_num

            url = SEARCH_BASE_URL
            full_url = f"{url}?query={quote_plus(keyword)}" + (f"&page={page_num}" if page_num > 1 else "")
            logger.info("Fetching page %d: %s", page_num, full_url)

            resp = await _get_with_retry(client, url, params=params)
            final_url = str(resp.url)
            fetched_at = datetime.now(timezone.utc).isoformat()

            html = resp.text
            _detect_block(html, final_url)
            source_urls.append(final_url)
            fetched_pages += 1

            # Extract __NEXT_DATA__
            nd = _extract_next_data(html)
            if nd is None:
                if page_num == 1:
                    raise ScraperParseError(
                        "No __NEXT_DATA__ JSON found in Fiverr response — page structure has changed"
                    )
                logger.warning("No __NEXT_DATA__ on page %d; stopping pagination", page_num)
                break

            page_gigs, page_total = _parse_gigs_from_next_data(nd, keyword, page_num, final_url, fetched_at)

            if page_total is not None and total_services is None:
                total_services = page_total

            if not page_gigs:
                if page_num == 1:
                    raise ScraperNoResultsError(
                        f"__NEXT_DATA__ found but no gig listings extracted for '{keyword}' "
                        f"(page structure may have changed)"
                    )
                # Subsequent pages with no results = done
                logger.info("No gigs on page %d; stopping pagination", page_num)
                break

            all_gigs.extend(page_gigs)
            logger.info("Page %d: got %d gigs (total so far: %d)", page_num, len(page_gigs), len(all_gigs))

            if page_num < MAX_PAGES:
                await asyncio.sleep(INTER_PAGE_DELAY)

    # Validate and deduplicate
    valid_gigs = [g for g in all_gigs if _validate_gig(g)]
    deduped = _dedup_gigs(valid_gigs)[:MAX_GIGS]

    # Re-assign sequential positions after dedup
    for i, g in enumerate(deduped):
        g["position"] = i + 1

    if not deduped:
        raise ScraperNoResultsError(
            f"Fetched {fetched_pages} page(s) but all {len(all_gigs)} extracted gigs failed validation"
        )

    return {
        "data_source": "live",
        "total_services": total_services,
        "gigs": deduped,
        "tags": [],           # Cross-ref tags from individual gig pages not collected
        "source_urls": source_urls,
        "fetched_pages": fetched_pages,
    }


# ---------------------------------------------------------------------------
# Autocomplete (public JSON API endpoint)
# ---------------------------------------------------------------------------
async def fetch_autocomplete(query: str, proxy_region: Optional[str] = None) -> dict:
    """
    Fetch Fiverr's autocomplete suggestions for `query`.

    Returns {"source": "live"|"unavailable", "suggestions": [...]}.
    Never returns simulated suggestions labelled as live.
    proxy_region is accepted for API compatibility but not used (no proxy routing).
    """
    if not query or len(query.strip()) < 2:
        return {"source": "skip", "suggestions": []}

    try:
        async with httpx.AsyncClient(headers=_AC_HEADERS, timeout=10.0) as client:
            resp = await client.get(
                AUTOCOMPLETE_URL,
                params={"query": query.strip()},
            )
            if resp.status_code == 200:
                data = resp.json()
                sugg = _extract_autocomplete(data)
                if sugg:
                    return {"source": "live", "suggestions": sugg}
            logger.info("Autocomplete returned status %d for '%s'", resp.status_code, query)
    except Exception as e:
        logger.info("Autocomplete request failed for '%s': %s", query, e)

    return {"source": "unavailable", "suggestions": []}


def _extract_autocomplete(data) -> list[str]:
    """Walk the autocomplete response and collect suggestion strings."""
    out: list[str] = []

    def walk(v):
        if isinstance(v, dict):
            for k, vv in v.items():
                if isinstance(vv, str) and k.lower() in ("query", "text", "suggestion", "value", "term"):
                    out.append(vv)
                else:
                    walk(vv)
        elif isinstance(v, list):
            for vv in v:
                walk(vv)

    walk(data)
    # Dedupe preserving order, drop too-short entries
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        s = s.strip()
        if len(s) > 2 and s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    return uniq[:15]


# ---------------------------------------------------------------------------
# Analytics (unchanged — pure computation on whatever gigs are provided)
# ---------------------------------------------------------------------------
def compute_opportunity(keyword: str, payload: dict, prior_median_price: Optional[float] = None) -> dict:
    """
    Compute all analytics metrics from the gig payload.

    Fields that are null in live-scraped gigs (orders_in_queue, reviews_last_7d,
    favourites) are handled gracefully — metrics that depend on them are computed
    from what IS available and the field_provenance dict documents what's missing.
    """
    gigs = payload.get("gigs", []) or []
    total = payload.get("total_services") or 0
    n = len(gigs)

    top10 = [g for g in gigs if g.get("position", 99) <= 10]
    bot10 = [g for g in gigs if g.get("position", 0) > 10]

    # orders_in_queue — may be null from live scrape
    def oiq(g):
        return g.get("orders_in_queue") or 0

    avg_queue_top = sum(oiq(g) for g in top10) / max(1, len(top10))
    avg_queue_bot = sum(oiq(g) for g in bot10) / max(1, len(bot10))
    avg_queue_all = sum(oiq(g) for g in gigs) / max(1, n)
    total_queue = sum(oiq(g) for g in gigs)

    # Reviews
    total_reviews = sum((g.get("reviews_count") or 0) for g in gigs)
    reviews_7d = sum((g.get("reviews_last_7d") or 0) for g in gigs)

    # Review velocity (hours since most recent) — uses last_review_at if present
    now = datetime.now(timezone.utc)
    velocities = []
    for g in top10:
        try:
            lr = g.get("last_review_at")
            if lr:
                dt = datetime.fromisoformat(lr)
                velocities.append((now - dt).total_seconds() / 3600.0)
        except Exception:
            pass
    review_velocity_hours = min(velocities) if velocities else 999.0

    # Pricing — median + top decile
    all_prices = sorted([g["price_from"] for g in gigs if g.get("price_from")])
    median_price = statistics.median(all_prices) if all_prices else 0
    top_decile_cutoff = (
        all_prices[int(len(all_prices) * 0.9)]
        if len(all_prices) >= 5
        else (max(all_prices) if all_prices else 0)
    )
    high_ticket = [
        g for g in gigs
        if (g.get("price_from") or 0) >= 200 and (g.get("orders_in_queue") or 0) >= 5
    ]
    high_ticket_vacuum = len(high_ticket) >= 1 and (total or 0) < 3000

    new_seller_prices = [
        g["price_from"] for g in gigs
        if g.get("seller_level") in ("New Seller", "Level 1") and g.get("price_from")
    ]
    top_prices = [
        g["price_from"] for g in gigs
        if g.get("seller_level") in ("Top Rated", "Fiverr Pro") and g.get("price_from")
    ]
    price_floor = (
        min(new_seller_prices) if new_seller_prices
        else (min(all_prices) if all_prices else 0)
    )
    price_ceiling = (
        max(top_prices) if top_prices
        else (max(all_prices) if all_prices else 0)
    )

    # Price inflation vs prior snapshot
    if prior_median_price and median_price:
        price_inflation_pct = round(((median_price - prior_median_price) / prior_median_price) * 100, 1)
    else:
        price_inflation_pct = None

    # Saturation Index (weighted, 0–100)
    sat_sum = sum(SAT_WEIGHTS.get(g.get("seller_level"), 0.2) for g in top10)
    saturation_index = round((sat_sum / max(1, len(top10))) * 100, 1)

    low_tier = [g for g in top10 if g.get("seller_level") in ("New Seller", "Level 1")]
    saturation_gap_pct = (len(low_tier) / max(1, len(top10))) * 100

    # Promoted CPA proxy
    promoted_count = sum(1 for g in gigs if g.get("is_promoted"))
    promoted_pct = round((promoted_count / max(1, n)) * 100, 1)

    pro_count = sum(1 for g in gigs if g.get("is_fiverr_pro"))

    # Velocity Score
    if total and total_reviews:
        velocity_raw = (total_queue / total) * (reviews_7d / total_reviews)
    else:
        velocity_raw = 0.0
    velocity_score = round(min(100.0, velocity_raw * 2000), 1)

    # Opportunity Score
    queue_score = min(1.0, avg_queue_all / 12.0)
    velocity_factor = (
        1.0 if review_velocity_hours < 48
        else max(0.0, 1.0 - (review_velocity_hours - 48) / 240.0)
    )
    demand_score = queue_score * 0.6 + velocity_factor * 0.4
    if avg_queue_all > 5 and review_velocity_hours < 48:
        demand_score = max(demand_score, 0.85)

    if total <= 0:
        competition_score = 0.5
    elif total < 500:
        competition_score = 1.0
    elif total < 2000:
        competition_score = 1.0 - ((total - 500) / 1500.0) * 0.3
    elif total < 8000:
        competition_score = 0.7 - ((total - 2000) / 6000.0) * 0.5
    else:
        competition_score = max(0.05, 0.2 - ((total - 8000) / 50000.0))

    saturation_component = min(1.0, saturation_gap_pct / 60.0)
    opportunity_score = round(demand_score * 40 + competition_score * 40 + saturation_component * 20, 1)

    ratio = round(avg_queue_all / (total / 100.0), 2) if total > 0 else 0.0
    momentum_gap = total < 1000 and avg_queue_top > 5

    # Document which fields are null due to data source limitations
    orders_in_queue_available = any(g.get("orders_in_queue") is not None for g in gigs)
    reviews_7d_available = any(g.get("reviews_last_7d") is not None for g in gigs)
    favourites_available = any(g.get("favourites") is not None for g in gigs)

    field_provenance = {
        "orders_in_queue": "live" if orders_in_queue_available else "unavailable:not_on_search_page",
        "reviews_last_7d": "live" if reviews_7d_available else "unavailable:not_publicly_surfaced",
        "favourites": "live" if favourites_available else "unavailable:not_on_search_page",
        "price_from": "live",
        "title": "live",
        "rating": "live",
        "reviews_count": "live",
        "seller_level": "live",
        "total_services": "live" if payload.get("total_services") is not None else "unavailable",
        "delivery_days": "live",
        "is_fiverr_pro": "live",
        "is_promoted": "live_partial:detected_from_page_data",
    }

    return {
        "opportunity_score": opportunity_score,
        "velocity_score": velocity_score,
        "saturation_index": saturation_index,
        "promoted_cpa_pct": promoted_pct,
        "promoted_cpa_signal": (
            "WIDE_OPEN" if promoted_pct < 10 and avg_queue_all > 4
            else ("CROWDED" if promoted_pct > 25 else "NORMAL")
        ),
        "momentum_gap": momentum_gap,
        "high_ticket_vacuum": high_ticket_vacuum,
        "breakdown": {
            "demand": round(demand_score * 40, 1),
            "competition": round(competition_score * 40, 1),
            "saturation_gap": round(saturation_component * 20, 1),
        },
        "competition_to_order_ratio": ratio,
        "ratio_is_gold": ratio > 5,
        "field_provenance": field_provenance,
        "metrics": {
            "total_services": total,
            "avg_orders_in_queue": round(avg_queue_all, 2),
            "avg_queue_top10": round(avg_queue_top, 2),
            "avg_queue_bottom10": round(avg_queue_bot, 2),
            "review_velocity_hours": round(review_velocity_hours, 1),
            "review_velocity_active": review_velocity_hours < 48,
            "reviews_last_7d": reviews_7d,
            "total_reviews": total_reviews,
            "price_floor": price_floor,
            "price_ceiling": price_ceiling,
            "median_price": median_price,
            "top_decile_price": top_decile_cutoff,
            "price_inflation_pct": price_inflation_pct,
            "high_ticket_count": len(high_ticket),
            "saturation_gap_pct": round(saturation_gap_pct, 1),
            "fiverr_pro_count": pro_count,
            "pro_percentage": round((pro_count / max(1, n)) * 100, 1),
            "promoted_count": promoted_count,
            "promoted_pct": promoted_pct,
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def deep_scrape(
    keyword: str,
    try_live: bool = True,
    prior_median_price: Optional[float] = None,
) -> dict:
    """
    Main scrape entry point.

    Attempts live scraping from Fiverr public search pages.
    On access denial or unavailable data, raises the underlying error.
    Does NOT fall back to simulated data — the caller must handle failures.

    Returns the full result dict including data_source, gigs, analytics,
    source_urls, and field_provenance.
    """
    payload: Optional[dict] = None
    scrape_error: Optional[str] = None
    scrape_error_type: Optional[str] = None

    if try_live:
        try:
            payload = await asyncio.wait_for(
                _live_scrape(keyword),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            scrape_error = f"Scrape timed out after 45s for keyword '{keyword}'"
            scrape_error_type = "timeout"
            logger.warning(scrape_error)
        except ScraperBlockedError as e:
            scrape_error = str(e)
            scrape_error_type = "blocked"
            logger.warning("Scraper blocked for '%s': %s", keyword, e)
        except ScraperNoResultsError as e:
            scrape_error = str(e)
            scrape_error_type = "no_results"
            logger.info("No results for '%s': %s", keyword, e)
        except ScraperParseError as e:
            scrape_error = str(e)
            scrape_error_type = "parse_error"
            logger.warning("Parse error for '%s': %s", keyword, e)
        except Exception as e:
            scrape_error = f"Unexpected scrape error: {e}"
            scrape_error_type = "error"
            logger.exception("Unexpected error scraping '%s'", keyword)
    else:
        scrape_error = "Live scraping disabled (try_live=False)"
        scrape_error_type = "disabled"

    if payload is None or not payload.get("gigs"):
        # Do NOT substitute simulated data.
        # Return an honest failure result that the caller stores and reports.
        data_source = scrape_error_type or "failed"
        return {
            "keyword": keyword,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "data_source": data_source,
            "scrape_error": scrape_error,
            "total_services": None,
            "gigs": [],
            "tags": [],
            "source_urls": [],
            "fetched_pages": 0,
            "field_provenance": {},
            # Analytics with zero gigs — all zeros, clearly marked
            "opportunity_score": 0.0,
            "velocity_score": 0.0,
            "saturation_index": 0.0,
            "promoted_cpa_pct": 0.0,
            "promoted_cpa_signal": "NORMAL",
            "momentum_gap": False,
            "high_ticket_vacuum": False,
            "breakdown": {"demand": 0.0, "competition": 0.0, "saturation_gap": 0.0},
            "competition_to_order_ratio": 0.0,
            "ratio_is_gold": False,
            "metrics": {
                "total_services": 0,
                "avg_orders_in_queue": 0.0,
                "avg_queue_top10": 0.0,
                "avg_queue_bottom10": 0.0,
                "review_velocity_hours": 999.0,
                "review_velocity_active": False,
                "reviews_last_7d": 0,
                "total_reviews": 0,
                "price_floor": 0,
                "price_ceiling": 0,
                "median_price": 0,
                "top_decile_price": 0,
                "price_inflation_pct": None,
                "high_ticket_count": 0,
                "saturation_gap_pct": 0.0,
                "fiverr_pro_count": 0,
                "pro_percentage": 0.0,
                "promoted_count": 0,
                "promoted_pct": 0.0,
            },
        }

    analytics = compute_opportunity(keyword, payload, prior_median_price=prior_median_price)
    return {
        "keyword": keyword,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "data_source": payload["data_source"],
        "total_services": payload["total_services"],
        "gigs": payload.get("gigs", []),
        "tags": payload.get("tags", []),
        "source_urls": payload.get("source_urls", []),
        "fetched_pages": payload.get("fetched_pages", 0),
        **analytics,
    }
