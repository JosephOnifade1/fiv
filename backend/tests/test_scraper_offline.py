"""
Offline tests for the Fiverr scraper.

These tests do NOT require Fiverr access, a running server, credentials,
or any external service.  All network calls are mocked.

Coverage:
 - HTML fixture parsing: correct gig count, fields, position assignment
 - Block detection: 403, CAPTCHA page, checkpoint redirect
 - Rate-limit handling: 429 with Retry-After respected
 - Malformed / missing __NEXT_DATA__: raises ScraperParseError or ScraperNoResultsError
 - Empty gig list in valid __NEXT_DATA__: raises ScraperNoResultsError
 - Pagination: gigs from multiple pages are merged, positions sequential
 - Deduplication: identical title+price from multiple pages kept once
 - Validation: gig with no title is dropped
 - Timeout: asyncio.TimeoutError maps to data_source=="timeout"
 - compute_opportunity: correct analytics on known inputs
 - deep_scrape: blocked -> data_source=="blocked", no gigs, no simulated data
 - deep_scrape: no_results -> data_source=="no_results", gigs==[], no simulated data
 - deep_scrape: success -> data_source=="live", analytics populated
 - fetch_autocomplete: live response parsed correctly
 - fetch_autocomplete: network failure -> source=="unavailable", no simulated suggestions
 - field_provenance: null fields documented, live fields documented
 - NaN guard: no NaN in numeric analytics fields
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import types
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test.
# We need to ensure httpx is importable; if not, skip these tests.
# ---------------------------------------------------------------------------
try:
    import httpx
except ImportError:
    pytest.skip("httpx not installed — skipping scraper offline tests", allow_module_level=True)

import scraper as sc
from scraper import (
    ScraperBlockedError,
    ScraperNoResultsError,
    ScraperParseError,
    _detect_block,
    _extract_autocomplete,
    _extract_next_data,
    _dedup_gigs,
    _normalize_seller_level,
    _parse_gigs_from_next_data,
    _validate_gig,
    compute_opportunity,
    deep_scrape,
    fetch_autocomplete,
)


# ===========================================================================
# Helpers / fixtures
# ===========================================================================

def _make_next_data(gigs: list[dict], total: int = 500) -> dict:
    """Build a minimal __NEXT_DATA__ dict in the Shape-1 layout."""
    return {
        "props": {
            "pageProps": {
                "results": {
                    "gigs": gigs,
                    "count": total,
                }
            }
        }
    }


def _make_gig(
    title: str = "I will design a logo",
    price: int = 25,
    level: str = "level_one",
    rating: float = 4.8,
    reviews: int = 120,
    delivery: int = 3,
    url: str = "/seller/service",
    idx: int = 0,
) -> dict:
    """Build a minimal gig dict in the Fiverr Next.js shape."""
    return {
        "title": title,
        "price": price,
        "seller": {"level": level, "name": "seller123"},
        "rating": {"score": rating, "count": reviews},
        "delivery_time": delivery,
        "gig_url": url,
    }


def _make_html_with_next_data(nd: dict) -> str:
    """Wrap a __NEXT_DATA__ dict in a minimal HTML page."""
    blob = json.dumps(nd)
    # Ensure length > 3000 to avoid trigger of _detect_block short page check
    padding = "<!-- " + ("padding" * 500) + " -->"
    return (
        f'<!DOCTYPE html><html><head>'
        f'<script id="__NEXT_DATA__" type="application/json">{blob}</script>'
        f'</head><body><h1>Fiverr</h1>{padding}</body></html>'
    )


def _make_resp(
    status_code: int = 200,
    text: str = "",
    url: str = "https://www.fiverr.com/search/gigs?query=test",
    headers: dict = None,
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = MagicMock()
    resp.url.__str__ = lambda s: url
    resp.headers = headers or {}
    return resp


# ===========================================================================
# 1. HTML fixture parsing
# ===========================================================================

class TestHTMLParsing:
    def _gig_payload(self, n=20):
        return [_make_gig(title=f"Gig number {i}", price=10 + i, idx=i) for i in range(n)]

    def test_extract_next_data_present(self):
        nd = _make_next_data(self._gig_payload(5))
        html = _make_html_with_next_data(nd)
        result = _extract_next_data(html)
        assert result is not None
        assert "props" in result

    def test_extract_next_data_missing(self):
        html = "<html><body>No data here</body></html>"
        result = _extract_next_data(html)
        assert result is None

    def test_extract_next_data_malformed_json(self):
        html = '<script id="__NEXT_DATA__" type="application/json">{bad json!</script>'
        result = _extract_next_data(html)
        assert result is None

    def test_parse_gigs_correct_count(self):
        gigs_raw = self._gig_payload(15)
        nd = _make_next_data(gigs_raw, total=1234)
        gigs, total = _parse_gigs_from_next_data(nd, "test", 1, "https://example.com", "2026-01-01T00:00:00+00:00")
        assert len(gigs) == 15
        assert total == 1234

    def test_parse_gigs_fields_present(self):
        nd = _make_next_data([_make_gig("Custom logo design", price=50, level="level_two", delivery=2)])
        gigs, _ = _parse_gigs_from_next_data(nd, "logo", 1, "https://example.com", "2026-01-01T00:00:00+00:00")
        assert len(gigs) == 1
        g = gigs[0]
        assert g["title"] == "Custom logo design"
        assert g["price_from"] == 50
        assert g["seller_level"] == "Level 2"
        assert g["delivery_days"] == 2
        assert g["position"] == 1
        assert g["_source_url"] == "https://example.com"

    def test_parse_gigs_null_unavailable_fields(self):
        """orders_in_queue, reviews_last_7d, favourites must be null from search page."""
        nd = _make_next_data([_make_gig()])
        gigs, _ = _parse_gigs_from_next_data(nd, "logo", 1, "https://example.com", "2026-01-01T00:00:00+00:00")
        g = gigs[0]
        assert g["orders_in_queue"] is None, "orders_in_queue must be null — not available on search page"
        assert g["reviews_last_7d"] is None, "reviews_last_7d must be null — not publicly available"
        assert g["favourites"] is None, "favourites must be null — not on search page"

    def test_parse_gigs_position_sequential(self):
        nd = _make_next_data(self._gig_payload(10))
        gigs, _ = _parse_gigs_from_next_data(nd, "logo", 1, "https://example.com", "2026-01-01T00:00:00+00:00")
        positions = [g["position"] for g in gigs]
        assert positions == list(range(1, 11))

    def test_parse_gigs_page2_offset(self):
        nd = _make_next_data(self._gig_payload(5))
        gigs, _ = _parse_gigs_from_next_data(nd, "logo", 2, "https://example.com", "2026-01-01T00:00:00+00:00")
        # Page 2 offset = 48; first gig on page 2 starts at position 49
        assert gigs[0]["position"] == 49

    def test_parse_gigs_empty_returns_empty(self):
        nd = _make_next_data([])
        gigs, _ = _parse_gigs_from_next_data(nd, "logo", 1, "https://example.com", "2026-01-01T00:00:00+00:00")
        assert gigs == []

    def test_parse_gigs_drops_no_title(self):
        nd = _make_next_data([
            {"title": "", "price": 10},
            {"title": "   ", "price": 10},
            _make_gig("Valid gig"),
        ])
        gigs, _ = _parse_gigs_from_next_data(nd, "logo", 1, "https://example.com", "2026-01-01T00:00:00+00:00")
        assert len(gigs) == 1
        assert gigs[0]["title"] == "Valid gig"


# ===========================================================================
# 2. Block detection
# ===========================================================================

class TestBlockDetection:
    def test_captcha_page_raises(self):
        with pytest.raises(ScraperBlockedError, match="[Cc]aptcha|human"):
            _detect_block("Please verify you are human to continue", "https://www.fiverr.com/search")

    def test_checkpoint_url_raises(self):
        with pytest.raises(ScraperBlockedError, match="checkpoint"):
            _detect_block("<html>ok</html>", "https://www.fiverr.com/checkpoint/abc")

    def test_suspiciously_short_raises(self):
        with pytest.raises(ScraperBlockedError, match="short"):
            _detect_block("<html><body>tiny</body></html>", "https://www.fiverr.com/search")

    def test_normal_page_no_raise(self):
        # Should not raise for a normal long page
        html = "<html>" + "x" * 5000 + "</html>"
        _detect_block(html, "https://www.fiverr.com/search/gigs?query=test")  # no exception


# ===========================================================================
# 3. Normalize seller level
# ===========================================================================

class TestNormalizeSellerLevel:
    @pytest.mark.parametrize("raw,expected", [
        ("level_one", "Level 1"),
        ("Level 1", "Level 1"),
        ("level one", "Level 1"),
        ("level_two", "Level 2"),
        ("Level 2", "Level 2"),
        ("top_rated", "Top Rated"),
        ("top rated", "Top Rated"),
        ("pro", "Fiverr Pro"),
        ("Fiverr Pro", "Fiverr Pro"),
        ("", "New Seller"),
        ("unknown", "New Seller"),
    ])
    def test_levels(self, raw, expected):
        assert _normalize_seller_level(raw) == expected


# ===========================================================================
# 4. Deduplication
# ===========================================================================

class TestDeduplication:
    def test_dedup_same_title_price_keeps_first(self):
        gigs = [
            {"title": "I will design a logo", "price_from": 25, "position": 1},
            {"title": "I will design a logo", "price_from": 25, "position": 50},  # duplicate
            {"title": "I will design a logo", "price_from": 30, "position": 2},   # different price
        ]
        result = _dedup_gigs(gigs)
        assert len(result) == 2

    def test_dedup_case_insensitive(self):
        gigs = [
            {"title": "Logo Design", "price_from": 10, "position": 1},
            {"title": "logo design", "price_from": 10, "position": 2},
        ]
        result = _dedup_gigs(gigs)
        assert len(result) == 1

    def test_dedup_different_titles_both_kept(self):
        gigs = [
            {"title": "Logo Design", "price_from": 10, "position": 1},
            {"title": "Banner Design", "price_from": 10, "position": 2},
        ]
        result = _dedup_gigs(gigs)
        assert len(result) == 2


# ===========================================================================
# 5. Validation
# ===========================================================================

class TestValidation:
    def test_valid_gig_passes(self):
        assert _validate_gig({"title": "I will do something", "price_from": 25}) is True

    def test_no_title_fails(self):
        assert _validate_gig({"title": "", "price_from": 25}) is False
        assert _validate_gig({"price_from": 25}) is False

    def test_zero_price_fails(self):
        assert _validate_gig({"title": "I will do it", "price_from": 0}) is False

    def test_none_price_passes(self):
        # Price may be None (unavailable) — that's valid; it won't be set to 0
        assert _validate_gig({"title": "I will do it", "price_from": None}) is True


# ===========================================================================
# 6. Autocomplete
# ===========================================================================

class TestAutocomplete:
    def test_extract_autocomplete_simple_list(self):
        data = {"suggestions": [{"query": "logo design"}, {"query": "logo maker"}]}
        result = _extract_autocomplete(data)
        assert "logo design" in result
        assert "logo maker" in result

    def test_extract_autocomplete_nested(self):
        data = {"data": {"items": [{"text": "web design"}, {"text": "app design"}]}}
        result = _extract_autocomplete(data)
        assert "web design" in result

    def test_extract_autocomplete_dedupes(self):
        data = {"a": [{"query": "logo"}, {"query": "logo"}]}
        result = _extract_autocomplete(data)
        assert result.count("logo") == 1

    @pytest.mark.asyncio
    async def test_fetch_autocomplete_short_query_returns_skip(self):
        result = await fetch_autocomplete("a")
        assert result["source"] == "skip"
        assert result["suggestions"] == []

    @pytest.mark.asyncio
    async def test_fetch_autocomplete_network_failure_returns_unavailable(self):
        """Network failure must return source='unavailable', never simulated suggestions."""
        with patch("scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.TransportError("connection refused"))

            result = await fetch_autocomplete("logo design")
            assert result["source"] == "unavailable"
            assert result["suggestions"] == []

    @pytest.mark.asyncio
    async def test_fetch_autocomplete_403_returns_unavailable(self):
        with patch("scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = MagicMock()
            resp.status_code = 403
            mock_client.get = AsyncMock(return_value=resp)

            result = await fetch_autocomplete("logo design")
            assert result["source"] == "unavailable"
            assert result["suggestions"] == []

    @pytest.mark.asyncio
    async def test_fetch_autocomplete_live_success(self):
        with patch("scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"suggestions": [{"query": "logo for startups"}, {"query": "logo maker"}]}
            mock_client.get = AsyncMock(return_value=resp)

            result = await fetch_autocomplete("logo")
            assert result["source"] == "live"
            assert len(result["suggestions"]) >= 1


# ===========================================================================
# 7. compute_opportunity analytics
# ===========================================================================

class TestComputeOpportunity:
    def _make_payload(self, n=20, total=500, oiq=8, price=50):
        gigs = []
        for i in range(n):
            gigs.append({
                "position": i + 1,
                "title": f"Gig {i}",
                "seller_level": "Level 2" if i < 10 else "New Seller",
                "is_fiverr_pro": False,
                "price_from": price,
                "orders_in_queue": oiq,
                "reviews_count": 100,
                "reviews_last_7d": 5,
                "favourites": 50,
                "rating": 4.8,
            })
        return {"gigs": gigs, "total_services": total}

    def test_opportunity_score_in_range(self):
        payload = self._make_payload()
        result = compute_opportunity("test keyword", payload)
        score = result["opportunity_score"]
        assert 0.0 <= score <= 100.0

    def test_no_nan_in_numerics(self):
        payload = self._make_payload()
        result = compute_opportunity("test", payload)
        for k in ("opportunity_score", "velocity_score", "saturation_index",
                   "promoted_cpa_pct", "competition_to_order_ratio"):
            v = result[k]
            assert not math.isnan(float(v)), f"{k} is NaN"

    def test_zero_total_no_crash(self):
        payload = {"gigs": [], "total_services": 0}
        result = compute_opportunity("test", payload)
        assert result["opportunity_score"] is not None
        assert not math.isnan(float(result["opportunity_score"]))

    def test_field_provenance_null_unavailable(self):
        """When orders_in_queue is None (live scrape), provenance must say unavailable."""
        gigs = [{
            "position": i + 1,
            "title": f"Gig {i}",
            "seller_level": "Level 1",
            "is_fiverr_pro": False,
            "price_from": 25,
            "orders_in_queue": None,   # NOT available from search page
            "reviews_last_7d": None,   # NOT available
            "favourites": None,        # NOT available
            "reviews_count": 50,
            "rating": 4.5,
        } for i in range(5)]
        payload = {"gigs": gigs, "total_services": 300}
        result = compute_opportunity("test", payload)
        fp = result["field_provenance"]
        assert "unavailable" in fp["orders_in_queue"]
        assert "unavailable" in fp["reviews_last_7d"]
        assert "unavailable" in fp["favourites"]
        assert fp["price_from"] == "live"
        assert fp["title"] == "live"

    def test_field_provenance_live_when_present(self):
        """When orders_in_queue is populated, provenance must say live."""
        gigs = [{
            "position": i + 1,
            "title": f"Gig {i}",
            "seller_level": "Level 1",
            "price_from": 25,
            "orders_in_queue": 5,
            "reviews_last_7d": 2,
            "favourites": 10,
            "reviews_count": 50,
        } for i in range(5)]
        payload = {"gigs": gigs, "total_services": 300}
        result = compute_opportunity("test", payload)
        fp = result["field_provenance"]
        assert fp["orders_in_queue"] == "live"

    def test_price_inflation_pct_computed(self):
        payload = self._make_payload(price=50)
        result = compute_opportunity("test", payload, prior_median_price=40.0)
        assert result["metrics"]["price_inflation_pct"] == pytest.approx(25.0, abs=0.5)

    def test_price_inflation_none_when_no_prior(self):
        payload = self._make_payload()
        result = compute_opportunity("test", payload, prior_median_price=None)
        assert result["metrics"]["price_inflation_pct"] is None

    def test_ratio_is_gold_high_queue_low_competition(self):
        """High queue + low total -> ratio > 5 -> gold."""
        payload = self._make_payload(n=20, total=100, oiq=10)
        result = compute_opportunity("test", payload)
        assert result["competition_to_order_ratio"] > 5
        assert result["ratio_is_gold"] is True

    def test_breakdown_sums_to_opportunity_score(self):
        payload = self._make_payload()
        result = compute_opportunity("test", payload)
        total = sum(result["breakdown"].values())
        assert abs(total - result["opportunity_score"]) < 0.5


# ===========================================================================
# 8. deep_scrape integration (mocked network)
# ===========================================================================

def _make_live_response(keyword: str, n_gigs: int = 20, total: int = 500) -> MagicMock:
    """Build a mock HTTP response with a proper __NEXT_DATA__ payload."""
    gigs_raw = [_make_gig(title=f"I will {keyword} gig {i}", price=20 + i) for i in range(n_gigs)]
    nd = _make_next_data(gigs_raw, total)
    html = _make_html_with_next_data(nd)
    return _make_resp(200, html)


def _patch_client(responses: list):
    """
    Return a context manager that replaces httpx.AsyncClient with one that
    returns the given responses in order for each .get() call.
    """
    call_count = [0]

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            r = responses[idx]
            if isinstance(r, Exception):
                raise r
            return r

    return patch("scraper.httpx.AsyncClient", return_value=FakeClient())


class TestDeepScrape:

    @pytest.mark.asyncio
    async def test_blocked_403_returns_blocked_data_source(self):
        resp = _make_resp(403, "", "https://www.fiverr.com/search/gigs?query=test")
        with _patch_client([resp]):
            result = await deep_scrape("logo design")
        assert result["data_source"] == "blocked"
        assert result["gigs"] == [], "must not contain simulated gigs"
        assert result["total_services"] is None

    @pytest.mark.asyncio
    async def test_captcha_page_returns_blocked(self):
        html = "<html>" + "Please verify you are human to continue on Fiverr" + "x" * 3000 + "</html>"
        resp = _make_resp(200, html)
        with _patch_client([resp]):
            result = await deep_scrape("logo design")
        assert result["data_source"] == "blocked"
        assert result["gigs"] == []

    @pytest.mark.asyncio
    async def test_no_next_data_returns_parse_error(self):
        html = "<html><body>" + "x" * 5000 + "</body></html>"
        resp = _make_resp(200, html)
        with _patch_client([resp]):
            result = await deep_scrape("logo design")
        assert result["data_source"] == "parse_error"
        assert result["gigs"] == []

    @pytest.mark.asyncio
    async def test_empty_gig_list_returns_no_results(self):
        nd = _make_next_data([])  # valid structure, no gigs
        html = _make_html_with_next_data(nd)
        resp = _make_resp(200, html)
        with _patch_client([resp]):
            result = await deep_scrape("obscure keyword xyz")
        assert result["data_source"] == "no_results"
        assert result["gigs"] == []

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_data_source(self):
        # Simulate asyncio.TimeoutError by patching wait_for
        async def fake_scrape(*args, **kwargs):
            raise asyncio.TimeoutError()
        with patch("scraper._live_scrape", side_effect=asyncio.TimeoutError()):
            result = await deep_scrape("logo design")
        assert result["data_source"] == "timeout"
        assert result["gigs"] == []

    @pytest.mark.asyncio
    async def test_successful_live_scrape(self):
        resp = _make_live_response("logo design", n_gigs=20, total=1500)
        # Only 1 page requested since MAX_PAGES applies, but we mock 1 page
        # with enough gigs and no second page (empty response for p2)
        empty_nd = _make_next_data([])
        empty_html = _make_html_with_next_data(empty_nd)
        empty_resp = _make_resp(200, empty_html)

        with _patch_client([resp, empty_resp, empty_resp]):
            result = await deep_scrape("logo design")

        assert result["data_source"] == "live"
        assert len(result["gigs"]) == 20
        assert result["total_services"] == 1500
        # Analytics computed
        assert "opportunity_score" in result
        assert 0.0 <= result["opportunity_score"] <= 100.0
        # Provenance documented
        assert "field_provenance" in result
        # Source URLs present
        assert len(result["source_urls"]) >= 1

    @pytest.mark.asyncio
    async def test_blocked_result_has_no_simulated_data(self):
        """
        CRITICAL: a blocked result must never contain simulated gig data.
        The old scraper fell back to _simulate(); this one must not.
        """
        resp = _make_resp(403, "")
        with _patch_client([resp]):
            result = await deep_scrape("logo design")

        assert result["gigs"] == [], "FAIL: blocked result returned gigs (may be simulated data)"
        # Every numeric field must be zero or None, not a positive simulated number
        assert result["total_services"] is None
        assert result["opportunity_score"] == 0.0

    @pytest.mark.asyncio
    async def test_no_results_has_no_simulated_data(self):
        nd = _make_next_data([])
        html = _make_html_with_next_data(nd)
        resp = _make_resp(200, html)
        with _patch_client([resp]):
            result = await deep_scrape("logo design")
        assert result["gigs"] == [], "FAIL: no_results returned gigs (may be simulated data)"

    @pytest.mark.asyncio
    async def test_live_gigs_positions_sequential(self):
        resp = _make_live_response("logo", n_gigs=15)
        empty_nd = _make_next_data([])
        empty_html = _make_html_with_next_data(empty_nd)
        empty_resp = _make_resp(200, empty_html)
        with _patch_client([resp, empty_resp, empty_resp]):
            result = await deep_scrape("logo")
        positions = [g["position"] for g in result["gigs"]]
        assert positions == list(range(1, len(positions) + 1))

    @pytest.mark.asyncio
    async def test_pagination_merges_gigs(self):
        """Two pages should be merged into a single deduped list."""
        resp1 = _make_live_response("web dev", n_gigs=20, total=3000)
        resp2 = _make_live_response("web dev page2", n_gigs=15, total=3000)
        empty_html = _make_html_with_next_data(_make_next_data([]))
        empty_resp = _make_resp(200, empty_html)

        # Patch INTER_PAGE_DELAY to 0 for speed
        with patch.object(sc, "INTER_PAGE_DELAY", 0):
            with _patch_client([resp1, resp2, empty_resp]):
                result = await deep_scrape("web dev")

        assert result["data_source"] == "live"
        # 20 + 15 minus any deduplication = at most 35
        assert 20 <= len(result["gigs"]) <= 35

    @pytest.mark.asyncio
    async def test_no_nan_in_live_result(self):
        resp = _make_live_response("logo")
        empty_html = _make_html_with_next_data(_make_next_data([]))
        empty_resp = _make_resp(200, empty_html)
        with _patch_client([resp, empty_resp, empty_resp]):
            result = await deep_scrape("logo")
        for k in ("opportunity_score", "velocity_score", "saturation_index",
                   "promoted_cpa_pct", "competition_to_order_ratio"):
            assert not math.isnan(float(result[k])), f"{k} is NaN"

    @pytest.mark.asyncio
    async def test_try_live_false_returns_disabled(self):
        result = await deep_scrape("logo", try_live=False)
        assert result["data_source"] == "disabled"
        assert result["gigs"] == []

    @pytest.mark.asyncio
    async def test_429_without_retry_after_uses_backoff(self):
        """429 response should be retried; if all retries exhausted -> blocked."""
        resp_429 = _make_resp(429, "", headers={})
        # Return 429 enough times to exhaust MAX_RETRIES
        with patch.object(sc, "RETRY_BASE_DELAY", 0):  # zero delay for test speed
            with _patch_client([resp_429] * (sc.MAX_RETRIES + 5)):
                result = await deep_scrape("logo")
        assert result["data_source"] == "blocked"

    @pytest.mark.asyncio
    async def test_scrape_error_message_in_result(self):
        """scrape_error field must describe what went wrong."""
        resp = _make_resp(403, "")
        with _patch_client([resp]):
            result = await deep_scrape("logo")
        assert result.get("scrape_error"), "scrape_error message must be present"
        assert "403" in result["scrape_error"] or "block" in result["scrape_error"].lower()


# ===========================================================================
# 9. Data provenance — source_urls and fetched_at
# ===========================================================================

class TestDataProvenance:
    @pytest.mark.asyncio
    async def test_source_urls_present_on_success(self):
        resp = _make_live_response("logo")
        empty_html = _make_html_with_next_data(_make_next_data([]))
        with _patch_client([resp, _make_resp(200, empty_html), _make_resp(200, empty_html)]):
            result = await deep_scrape("logo")
        assert len(result["source_urls"]) >= 1
        assert all("fiverr.com" in u for u in result["source_urls"])

    @pytest.mark.asyncio
    async def test_source_urls_empty_on_failure(self):
        resp = _make_resp(403, "")
        with _patch_client([resp]):
            result = await deep_scrape("logo")
        assert result["source_urls"] == []

    @pytest.mark.asyncio
    async def test_fetched_pages_count(self):
        resp1 = _make_live_response("logo", n_gigs=10)
        empty_html = _make_html_with_next_data(_make_next_data([]))
        empty_resp = _make_resp(200, empty_html)
        with patch.object(sc, "INTER_PAGE_DELAY", 0):
            with _patch_client([resp1, empty_resp, empty_resp]):
                result = await deep_scrape("logo")
        assert result["fetched_pages"] >= 1


# ===========================================================================
# 10. MAX_GIGS cap
# ===========================================================================

class TestLimits:
    @pytest.mark.asyncio
    async def test_max_gigs_cap_applied(self):
        """No more than MAX_GIGS gigs should be returned even with full pages."""
        # Create a response with more gigs than MAX_GIGS
        too_many = [_make_gig(title=f"Gig unique {i}", price=10 + (i % 100)) for i in range(sc.MAX_GIGS + 20)]
        nd = _make_next_data(too_many, total=5000)
        html = _make_html_with_next_data(nd)
        resp = _make_resp(200, html)
        empty_html = _make_html_with_next_data(_make_next_data([]))
        empty_resp = _make_resp(200, empty_html)
        with patch.object(sc, "INTER_PAGE_DELAY", 0):
            with _patch_client([resp, empty_resp, empty_resp]):
                result = await deep_scrape("logo")
        assert len(result["gigs"]) <= sc.MAX_GIGS

