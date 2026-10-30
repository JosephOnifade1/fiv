"""Backend tests for Fiverr Niche Arbitrage Scout (iteration 2)."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opportunity-harvest.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@fiverrscout.example.com"
DEMO_PASS = "Demo1234!"

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

state = {}


def auth_header():
    return {"Authorization": f"Bearer {state['token']}"}


# -------- Auth & health (smoke) --------
def test_01_health():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_02_register_or_login():
    r = session.post(f"{API}/auth/register", json={"email": DEMO_EMAIL, "password": DEMO_PASS, "name": "Demo"})
    if r.status_code == 400:
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    assert r.status_code == 200, r.text
    data = r.json()
    state["token"] = data["token"]
    state["user_id"] = data["user"]["id"]


def test_03_me():
    r = requests.get(f"{API}/auth/me", headers=auth_header())
    assert r.status_code == 200
    assert r.json()["email"] == DEMO_EMAIL


def test_04_protected_without_token():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code in (401, 403)


def test_05_register_duplicate():
    r = session.post(f"{API}/auth/register", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    assert r.status_code == 400


def test_06_login_bad_password():
    r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"})
    assert r.status_code == 401


# -------- Scrape job lifecycle + new 2026 fields --------
def _wait_job(job_id, timeout=40):
    for _ in range(timeout):
        time.sleep(1)
        rr = requests.get(f"{API}/scrape/jobs/{job_id}", headers=auth_header())
        assert rr.status_code == 200
        doc = rr.json()
        if doc["status"] in ("complete", "failed"):
            return doc
    pytest.fail("Job did not finish in time")


def test_07_scrape_search_with_2026_fields():
    r = requests.post(f"{API}/scrape/search", json={"keyword": "logo design minimalist"}, headers=auth_header())
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    state["job_id"] = job_id
    final = _wait_job(job_id, timeout=60)
    res = final["result"]

    # The job must terminate (complete OR failed-with-access-denied).
    # Both are valid — the live scraper reports access honestly.
    assert final["status"] in ("complete", "failed"), f"unexpected status: {final}"

    # data_source must be one of the known honest values
    ds = res.get("data_source", "")
    assert ds in ("live", "blocked", "timeout", "no_results", "parse_error", "error", "disabled"),         f"unexpected data_source: {ds!r}"

    # Core analytics fields must always be present regardless of data source
    assert "opportunity_score" in res
    assert "breakdown" in res
    for k in ("demand", "competition", "saturation_gap"):
        assert k in res["breakdown"]
    assert "competition_to_order_ratio" in res
    assert "ratio_is_gold" in res

    # 2026 top-level metrics must always be present
    assert "velocity_score" in res and isinstance(res["velocity_score"], (int, float))
    assert "saturation_index" in res and isinstance(res["saturation_index"], (int, float))
    assert "promoted_cpa_pct" in res and isinstance(res["promoted_cpa_pct"], (int, float))
    assert "promoted_cpa_signal" in res
    assert res["promoted_cpa_signal"] in ("WIDE_OPEN", "NORMAL", "CROWDED")
    assert "momentum_gap" in res and isinstance(res["momentum_gap"], bool)
    assert "high_ticket_vacuum" in res and isinstance(res["high_ticket_vacuum"], bool)

    # Numeric guards: no NaN
    import math
    for k in ("velocity_score", "saturation_index", "promoted_cpa_pct", "opportunity_score"):
        assert not math.isnan(float(res[k])), f"{k} is NaN"

    # Metrics block must always be present
    m = res["metrics"]
    for k in ("reviews_last_7d", "total_reviews", "median_price",
              "top_decile_price", "price_inflation_pct", "high_ticket_count",
              "promoted_count", "promoted_pct"):
        assert k in m, f"missing metric {k}"

    # When live data was collected, validate gig-level shape
    gigs = res.get("gigs", [])
    if gigs:
        assert 1 <= len(gigs) <= 60, f"unexpected gig count: {len(gigs)}"
        g0 = gigs[0]
        # These fields must exist (may be None if not on search page)
        for k in ("reviews_last_7d", "favourites", "is_promoted"):
            assert k in g0, f"missing gig field {k}"
        # title, position, price_from must be present and valid
        assert g0.get("title"), "gig title must be non-empty"
        assert g0.get("position") == 1, "first gig position must be 1"
    else:
        # Access denied or no listings — verify honest failure is documented
        assert ds in ("blocked", "timeout", "no_results", "parse_error"),             f"empty gigs but data_source is {ds!r} — possible silent simulation"
        assert res.get("scrape_error") or ds == "no_results",             "blocked result must carry scrape_error message"

    # Provenance fields must be present when live
    if ds == "live":
        assert res.get("source_urls"), "live result must have source_urls"
        assert res.get("fetched_pages", 0) >= 1, "live result must report fetched_pages"
        assert "field_provenance" in res, "live result must have field_provenance"

    state["keyword"] = final["keyword"]


def test_08_jobs_list():
    r = requests.get(f"{API}/scrape/jobs", headers=auth_header())
    assert r.status_code == 200
    items = r.json()
    assert any(it["id"] == state["job_id"] for it in items)


def test_09_export_csv_has_favourites():
    r = requests.get(f"{API}/scrape/jobs/{state['job_id']}/export?format=csv", headers=auth_header())
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "attachment" in r.headers.get("content-disposition", "")
    # Header row must include favourites column
    first_line = r.text.splitlines()[0]
    assert "favourites" in first_line, f"favourites column missing in CSV header: {first_line}"
    assert "OPPORTUNITY_SCORE" in r.text


def test_10_export_json():
    r = requests.get(f"{API}/scrape/jobs/{state['job_id']}/export?format=json", headers=auth_header())
    assert r.status_code == 200
    body = r.json()
    assert "opportunity_score" in body
    assert "velocity_score" in body


def test_11_watchlist_crud():
    r = requests.post(f"{API}/watchlist", json={"keyword": state["keyword"], "note": "test"}, headers=auth_header())
    assert r.status_code == 200
    wid = r.json()["id"]
    r2 = requests.get(f"{API}/watchlist", headers=auth_header())
    assert r2.status_code == 200
    found = next((i for i in r2.json() if i["id"] == wid), None)
    assert found is not None
    assert found.get("latest_snapshot") is not None
    r3 = requests.delete(f"{API}/watchlist/{wid}", headers=auth_header())
    assert r3.status_code == 200


def test_12_trends_has_median_and_saturation():
    r = requests.get(f"{API}/trends/{state['keyword']}", headers=auth_header())
    assert r.status_code == 200
    snaps = r.json()["snapshots"]
    assert len(snaps) >= 1
    # last snapshot has new fields
    s = snaps[-1]
    assert "velocity_score" in s
    assert "median_price" in s
    assert "saturation_index" in s


def test_13_focus_keywords_sorts():
    for sb in ("opportunity_score", "orders", "favourites", "reviews"):
        r = requests.get(f"{API}/focus-keywords?sort_by={sb}", headers=auth_header())
        assert r.status_code == 200
        body = r.json()
        assert body["sort_by"] == sb
        assert isinstance(body["items"], list)


# -------- NEW: /api/autocomplete --------
def test_14_autocomplete_valid_query():
    r = requests.post(f"{API}/autocomplete", json={"query": "logo design"}, headers=auth_header(), timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "source" in body
    assert "suggestions" in body
    assert isinstance(body["suggestions"], list)
    assert len(body["suggestions"]) >= 1


def test_15_autocomplete_short_query_skip():
    r = requests.post(f"{API}/autocomplete", json={"query": "a"}, headers=auth_header())
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "skip"
    assert body["suggestions"] == []


def test_16_autocomplete_requires_auth():
    r = requests.post(f"{API}/autocomplete", json={"query": "logo"})
    assert r.status_code in (401, 403)


# -------- NEW: AI endpoints --------
def test_17_ai_trend_verdict():
    r = requests.post(f"{API}/ai/trend-verdict", json={"job_id": state["job_id"]}, headers=auth_header(), timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "verdict" in body
    assert body["verdict"] in ("FLASH_IN_PAN", "LONG_TERM_SURGE", "NEUTRAL")
    assert "matched_trend" in body
    assert "horizon_months" in body
    assert "reasoning" in body


def test_18_ai_proximity():
    r = requests.post(f"{API}/ai/proximity"
                      , json={"job_id": state["job_id"]}, headers=auth_header(), timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "autocomplete" in body
    assert "suggestions" in body["autocomplete"]
    assert "map" in body
    assert "sidesteps" in body["map"]
    assert isinstance(body["map"]["sidesteps"], list)


def test_19_ai_trend_verdict_bad_job():
    r = requests.post(f"{API}/ai/trend-verdict", json={"job_id": str(uuid.uuid4())}, headers=auth_header())
    assert r.status_code == 404


def test_20_ai_summarize_existing():
    r = requests.post(f"{API}/ai/summarize", json={"job_id": state["job_id"]}, headers=auth_header(), timeout=60)
    assert r.status_code == 200
    body = r.json()
    assert "bullets" in body and "verdict" in body


def test_21_price_inflation_after_second_scan():
    # Run a 2nd scan of same keyword to populate price_inflation_pct
    r = requests.post(f"{API}/scrape/search", json={"keyword": state["keyword"]}, headers=auth_header())
    job_id = r.json()["job_id"]
    final = _wait_job(job_id, timeout=60)
    res = final["result"]
    assert "price_inflation_pct" in res["metrics"]
    # On 2nd run: if live data was collected and prior median exists, price_inflation_pct is numeric.
    # If access was denied, it may be None — that is honest behaviour.
    pct = res["metrics"]["price_inflation_pct"]
    ds = res.get("data_source", "")
    if ds == "live":
        assert pct is not None, "live 2nd scan must compute price_inflation_pct"
    # If blocked, None is acceptable — do not assert non-None on denied access
