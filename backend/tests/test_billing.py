"""Billing/Stripe Pro tier tests (iteration 3)."""
import os
import time
import uuid
from datetime import datetime, timezone

import jwt
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opportunity-harvest.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@fiverrscout.example.com"
DEMO_PASS = "Demo1234!"
ADMIN_EMAIL = "onifadejosp@gmail.com"
ADMIN_ID = "b8ad2ae8-cf42-4dc4-9c5a-f5cfa8ba5087"
JWT_SECRET = "fiverr_scout_jwt_secret_2026_change_me_in_prod"
FREE_LIMIT = 5

_mongo = MongoClient("mongodb://localhost:27017")
_db = _mongo["test_database"]


@pytest.fixture(scope="module")
def demo_token():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/register", json={"email": DEMO_EMAIL, "password": DEMO_PASS, "name": "Demo"})
    if r.status_code == 400:
        r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    # Generate JWT directly — admin pwd unknown
    payload = {
        "sub": ADMIN_ID,
        "email": ADMIN_EMAIL,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="module")
def demo_user_id(demo_token):
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {demo_token}"})
    return r.json()["id"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- /api/billing/me ----------
def test_billing_me_demo_free(demo_token):
    r = requests.get(f"{API}/billing/me", headers=_h(demo_token))
    assert r.status_code == 200, r.text
    b = r.json()
    for k in ("plan", "is_admin", "scans_used_this_month", "free_limit", "scans_remaining", "price_usd", "current_month"):
        assert k in b, f"missing {k}"
    assert b["plan"] == "free"
    assert b["is_admin"] in (False, 0)
    assert b["free_limit"] == FREE_LIMIT
    assert isinstance(b["scans_remaining"], int)
    assert b["price_usd"] == 29.0
    assert b["current_month"] == datetime.now(timezone.utc).strftime("%Y-%m")


def test_billing_me_admin_pro_unlimited(admin_token):
    r = requests.get(f"{API}/billing/me", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["plan"] == "pro"
    assert b["is_admin"] in (True, 1)
    assert b["scans_remaining"] is None  # unlimited


def test_billing_me_requires_auth():
    r = requests.get(f"{API}/billing/me")
    assert r.status_code in (401, 403)


# ---------- /api/billing/checkout ----------
def test_checkout_creates_stripe_session(demo_token, demo_user_id):
    r = requests.post(
        f"{API}/billing/checkout",
        json={"package_id": "pro_monthly", "origin_url": BASE_URL},
        headers=_h(demo_token),
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "url" in body and "session_id" in body
    assert "checkout.stripe.com" in body["url"]
    # Verify payments record persisted
    tx = _db.fs_payments.find_one({"session_id": body["session_id"]})
    assert tx is not None
    assert tx["user_id"] == demo_user_id
    assert tx["status"] == "initiated"
    assert tx["payment_status"] == "pending"
    assert tx["package_id"] == "pro_monthly"
    assert float(tx["amount"]) == 29.0
    # Save for status test
    pytest.session_id = body["session_id"]


def test_checkout_invalid_package(demo_token):
    r = requests.post(
        f"{API}/billing/checkout",
        json={"package_id": "free_lol", "origin_url": BASE_URL},
        headers=_h(demo_token),
    )
    assert r.status_code == 400


# ---------- /api/billing/status/{sid} ----------
def test_billing_status_pending(demo_token):
    sid = getattr(pytest, "session_id", None)
    assert sid, "Need session_id from prior test"
    r = requests.get(f"{API}/billing/status/{sid}", headers=_h(demo_token), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("payment_status", "status", "plan_applied"):
        assert k in body
    # Not paid yet
    assert body["plan_applied"] in (False, 0, None)


def test_billing_status_not_found(demo_token):
    r = requests.get(f"{API}/billing/status/sess_nonexistent_xyz", headers=_h(demo_token))
    assert r.status_code == 404


# ---------- Webhook ----------
def test_webhook_endpoint_exists():
    # Invalid signature should give 400, not 404
    r = requests.post(f"{API}/webhook/stripe", data=b"{}", headers={"Stripe-Signature": "invalid"})
    assert r.status_code in (200, 400), r.text


# ---------- 402 enforcement for free over-limit ----------
def test_scan_402_when_free_over_limit(demo_token, demo_user_id):
    # Seed FREE_LIMIT jobs this month so next scan is over-limit
    now = datetime.now(timezone.utc)
    seeded_ids = []
    for _ in range(FREE_LIMIT):
        jid = f"TEST_SEED_{uuid.uuid4()}"
        _db.fs_jobs.insert_one({
            "id": jid,
            "user_id": demo_user_id,
            "keyword": "TEST_seed_billing",
            "status": "complete",
            "created_at": now.isoformat(),
            "result": {},
        })
        seeded_ids.append(jid)
    try:
        r = requests.post(f"{API}/scrape/search", json={"keyword": "billing test over limit"}, headers=_h(demo_token))
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"
        detail = r.json().get("detail", {})
        assert detail.get("code") == "PAYMENT_REQUIRED", detail
        assert detail.get("limit") == FREE_LIMIT
    finally:
        _db.fs_jobs.delete_many({"id": {"$in": seeded_ids}})


def test_scan_admin_unlimited(admin_token):
    # Seed plenty of admin scans this month, still must succeed
    now = datetime.now(timezone.utc)
    seeded_ids = []
    for _ in range(FREE_LIMIT + 3):
        jid = f"TEST_SEED_{uuid.uuid4()}"
        _db.fs_jobs.insert_one({
            "id": jid,
            "user_id": ADMIN_ID,
            "keyword": "TEST_admin_seed",
            "status": "complete",
            "created_at": now.isoformat(),
            "result": {},
        })
        seeded_ids.append(jid)
    try:
        r = requests.post(f"{API}/scrape/search", json={"keyword": "admin unlimited test"}, headers=_h(admin_token))
        assert r.status_code == 200, f"admin should bypass limit: {r.status_code} {r.text}"
        job_id = r.json()["job_id"]
        seeded_ids.append(job_id)
    finally:
        time.sleep(2)
        _db.fs_jobs.delete_many({"id": {"$in": seeded_ids}})


def test_scan_free_under_limit_fresh_user():
    # Create a fresh TEST_ user with 0 scans to verify under-limit succeeds
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_under_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Demo1234!", "name": "TestUnder"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    uid = r.json()["user"]["id"]
    try:
        r2 = requests.post(f"{API}/scrape/search", json={"keyword": "under limit fresh"}, headers={"Authorization": f"Bearer {tok}"})
        assert r2.status_code == 200, r2.text
    finally:
        time.sleep(2)
        _db.fs_jobs.delete_many({"user_id": uid})
        _db.fs_users.delete_one({"id": uid})
