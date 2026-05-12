"""Iteration 4 — Live niches pipeline tests (POST /api/scan, /api/niches, /api/scan/{tid})."""
import os
import time
import uuid
import jwt
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://opportunity-harvest.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
JWT_SECRET = "fiverr_scout_jwt_secret_2026_change_me_in_prod"
ADMIN_SUB = "b8ad2ae8-cf42-4dc4-9c5a-f5cfa8ba5087"
ADMIN_EMAIL = "onifadejosp@gmail.com"
GOLD_KEYWORD = "agentic AI workflow design"  # 4-word -> total<900; deterministic seed


def _admin_token():
    payload = {
        "sub": ADMIN_SUB,
        "email": ADMIN_EMAIL,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_admin_token()}",
                      "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def fresh_user_client():
    """Register a unique TEST_ user to avoid quota collisions."""
    email = f"TEST_live_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "Testpass123!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pwd, "name": "LiveTester"})
    assert r.status_code in (200, 400), r.text
    if r.status_code == 400:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    token = r.json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    s.email = email
    return s


def _wait_for_task(client, task_id, timeout=40):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        r = client.get(f"{API}/scan/{task_id}")
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") in ("complete", "failed"):
            return last
        time.sleep(1.5)
    return last


# ===== POST /api/scan =====
class TestScanTrigger:
    def test_scan_returns_task_id_shape(self, admin_client):
        r = admin_client.post(f"{API}/scan", json={"keyword": GOLD_KEYWORD})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "task_id" in d and isinstance(d["task_id"], str)
        assert d["status"] == "queued"
        assert d["keyword"] == GOLD_KEYWORD

    def test_scan_task_transitions_to_complete(self, admin_client):
        r = admin_client.post(f"{API}/scan", json={"keyword": GOLD_KEYWORD})
        tid = r.json()["task_id"]
        final = _wait_for_task(admin_client, tid)
        assert final is not None
        assert final["status"] == "complete", final
        assert "score" in final
        assert "is_gold" in final
        assert isinstance(final["is_gold"], bool)

    def test_scan_upsert_no_duplicate_increments_count(self, admin_client):
        # First scan
        r1 = admin_client.post(f"{API}/scan", json={"keyword": GOLD_KEYWORD})
        assert r1.status_code == 200
        _wait_for_task(admin_client, r1.json()["task_id"])
        # Capture niches state
        before = admin_client.get(f"{API}/niches?limit=100").json()
        rows_before = [x for x in before["items"] if x["keyword"] == GOLD_KEYWORD.lower()]
        assert len(rows_before) == 1, "should have single doc per keyword"
        sc_before = rows_before[0].get("scan_count", 0)

        # Second scan same keyword
        r2 = admin_client.post(f"{API}/scan", json={"keyword": GOLD_KEYWORD})
        _wait_for_task(admin_client, r2.json()["task_id"])
        after = admin_client.get(f"{API}/niches?limit=100").json()
        rows_after = [x for x in after["items"] if x["keyword"] == GOLD_KEYWORD.lower()]
        assert len(rows_after) == 1, "still single doc (upsert)"
        sc_after = rows_after[0].get("scan_count", 0)
        assert sc_after > sc_before, f"scan_count should increment: before={sc_before}, after={sc_after}"


# ===== GET /api/niches =====
class TestNichesBoard:
    def test_niches_shape(self, admin_client):
        # Ensure at least one doc
        r = admin_client.post(f"{API}/scan", json={"keyword": GOLD_KEYWORD})
        _wait_for_task(admin_client, r.json()["task_id"])
        rr = admin_client.get(f"{API}/niches?limit=20")
        assert rr.status_code == 200
        d = rr.json()
        assert "count" in d and "items" in d
        assert d["count"] == len(d["items"])
        if d["items"]:
            item = d["items"][0]
            for k in ["keyword", "display_keyword", "total_gigs", "avg_orders_in_queue",
                      "score", "is_gold", "last_scanned", "snapshot", "status"]:
                assert k in item, f"missing {k} in niche item: {item.keys()}"

    def test_niches_sorted_by_score_desc(self, admin_client):
        # Seed multiple keywords to ensure ordering
        for kw in ["agentic AI workflow design", "linkedin ghostwriting saas premium",
                   "notion template marketplace agency"]:
            r = admin_client.post(f"{API}/scan", json={"keyword": kw})
            _wait_for_task(admin_client, r.json()["task_id"], timeout=30)
        d = admin_client.get(f"{API}/niches?limit=20").json()
        scores = [(x.get("score") or 0) for x in d["items"] if x.get("status") == "complete"]
        assert scores == sorted(scores, reverse=True), f"not sorted DESC: {scores}"

    def test_gold_flag_logic(self, admin_client):
        d = admin_client.get(f"{API}/niches?limit=50").json()
        for it in d["items"]:
            if it.get("status") != "complete":
                continue
            expected = (it["total_gigs"] is not None and it["total_gigs"] < 500
                        and (it["avg_orders_in_queue"] or 0) > 8)
            assert it["is_gold"] == expected, f"gold mismatch on {it['keyword']}: {it}"

    def test_only_gold_filter(self, admin_client):
        d = admin_client.get(f"{API}/niches?limit=30&only_gold=true").json()
        for it in d["items"]:
            assert it.get("is_gold") is True

    def test_deterministic_gold_keyword(self, admin_client):
        """agentic AI workflow design should produce is_gold=true via simulator."""
        r = admin_client.post(f"{API}/scan", json={"keyword": GOLD_KEYWORD})
        _wait_for_task(admin_client, r.json()["task_id"])
        d = admin_client.get(f"{API}/niches?limit=100").json()
        row = next((x for x in d["items"] if x["keyword"] == GOLD_KEYWORD.lower()), None)
        assert row is not None
        # Deterministic simulator: for this 4-word keyword expect total<500 & avg>8
        # If not gold, surface the actual numbers in the assert error
        assert row["is_gold"] is True, f"expected gold but got: total={row.get('total_gigs')}, avg={row.get('avg_orders_in_queue')}"


# ===== Plan enforcement on /api/scan =====
class TestScanQuota:
    def test_admin_bypasses_limit(self, admin_client):
        # Admin should always get 200
        r = admin_client.post(f"{API}/scan", json={"keyword": f"admin probe {uuid.uuid4().hex[:6]}"})
        assert r.status_code == 200

    def test_free_user_402_after_limit(self, fresh_user_client):
        # Burn through 5 free scans then expect 402
        statuses = []
        for i in range(6):
            r = fresh_user_client.post(f"{API}/scan", json={"keyword": f"fresh scan {i} {uuid.uuid4().hex[:4]}"})
            statuses.append(r.status_code)
        assert statuses.count(200) >= 5
        assert 402 in statuses, f"expected a 402 in {statuses}"


# ===== Scan task 404 =====
def test_scan_task_404(admin_client):
    r = admin_client.get(f"{API}/scan/{uuid.uuid4()}")
    assert r.status_code == 404
