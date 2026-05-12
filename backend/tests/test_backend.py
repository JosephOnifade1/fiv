"""Backend tests for Fiverr Niche Arbitrage Scout."""
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
    assert "token" in data and "user" in data
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


def test_07_scrape_search_and_complete():
    r = requests.post(f"{API}/scrape/search", json={"keyword": "logo design minimalist"}, headers=auth_header())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "running"
    job_id = j["job_id"]
    state["job_id"] = job_id

    # Poll up to ~30s
    final = None
    for _ in range(30):
        time.sleep(1)
        rr = requests.get(f"{API}/scrape/jobs/{job_id}", headers=auth_header())
        assert rr.status_code == 200
        doc = rr.json()
        if doc["status"] in ("complete", "failed"):
            final = doc
            break
    assert final is not None, "Job did not finish in time"
    assert final["status"] == "complete", final
    res = final["result"]
    # Validate response schema
    assert "opportunity_score" in res
    assert "breakdown" in res
    for k in ("demand", "competition", "saturation_gap"):
        assert k in res["breakdown"]
    assert "competition_to_order_ratio" in res
    assert "ratio_is_gold" in res
    assert "metrics" in res
    assert len(res["gigs"]) == 20
    assert isinstance(res["tags"], list) and len(res["tags"]) > 0
    assert res["data_source"] in ("live", "simulated_fallback")
    state["keyword"] = final["keyword"]


def test_08_jobs_list():
    r = requests.get(f"{API}/scrape/jobs", headers=auth_header())
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert any(it["id"] == state["job_id"] for it in items)


def test_09_export_csv():
    r = requests.get(f"{API}/scrape/jobs/{state['job_id']}/export?format=csv", headers=auth_header())
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "attachment" in r.headers.get("content-disposition", "")
    assert "OPPORTUNITY_SCORE" in r.text


def test_10_export_json():
    r = requests.get(f"{API}/scrape/jobs/{state['job_id']}/export?format=json", headers=auth_header())
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")
    body = r.json()
    assert "opportunity_score" in body


def test_11_watchlist_add_list_delete():
    r = requests.post(f"{API}/watchlist", json={"keyword": state["keyword"], "note": "test"}, headers=auth_header())
    assert r.status_code == 200
    wid = r.json()["id"]

    r2 = requests.get(f"{API}/watchlist", headers=auth_header())
    assert r2.status_code == 200
    items = r2.json()
    found = next((i for i in items if i["id"] == wid), None)
    assert found is not None
    assert found.get("latest_snapshot") is not None
    assert "week_over_week_pct" in found  # may be None on first scan

    r3 = requests.delete(f"{API}/watchlist/{wid}", headers=auth_header())
    assert r3.status_code == 200


def test_12_trends():
    r = requests.get(f"{API}/trends/{state['keyword']}", headers=auth_header())
    assert r.status_code == 200
    body = r.json()
    assert "snapshots" in body
    assert len(body["snapshots"]) >= 1


def test_13_ai_expand():
    r = requests.post(f"{API}/ai/expand", json={"keyword": "logo design", "gig_titles": ["minimalist logo"]}, headers=auth_header(), timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "expansions" in body
    assert isinstance(body["expansions"], list)


def test_14_ai_summarize():
    r = requests.post(f"{API}/ai/summarize", json={"job_id": state["job_id"]}, headers=auth_header(), timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "bullets" in body
    assert "verdict" in body


def test_15_ai_pivots():
    r = requests.post(f"{API}/ai/pivots", json={"job_id": state["job_id"]}, headers=auth_header(), timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "pivots" in body


def test_16_get_job_not_found():
    r = requests.get(f"{API}/scrape/jobs/{uuid.uuid4()}", headers=auth_header())
    assert r.status_code == 404
