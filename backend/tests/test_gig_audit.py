# Gig Audit (iteration 6) — POST /api/gigs/audit, before score, issues, free locking, validation, list kind, build regression
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PRO = ("pro@fiverrscout.example.com", "Pro1234!")
DEMO = ("demo@fiverrscout.example.com", "Demo1234!")
STATE = {}

ORIGINAL = {
    "title": "I will do a logo for you",
    "tags": ["logo", "design", "cheap logo"],
    "description": "Hi, I make logos. Contact me on WhatsApp or email me for details. Fast and cheap.",
    "packages": [
        {"tier": "Basic", "name": "Basic", "description": "1 logo", "price": 10, "delivery_days": 2},
        {"tier": "Standard", "name": "Standard", "description": "2 logos", "price": 20, "delivery_days": 3},
        {"tier": "Premium", "name": "Premium", "description": "3 logos", "price": 30, "delivery_days": 4},
    ],
    "faq": [{"question": "Do you give source files?", "answer": "Yes, for premium."}],
}


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code}")
    d = r.json()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {d.get('token') or d.get('access_token')}"})
    return s


@pytest.fixture(scope="module")
def pro():
    return _login(*PRO)


@pytest.fixture(scope="module")
def demo():
    return _login(*DEMO)


def _job(sess, kw="minimalist logo design"):
    jobs = sess.get(f"{API}/scrape/jobs", timeout=30).json()
    for j in jobs:
        if j["status"] == "complete" and j["keyword"].lower() == kw:
            return j["id"]
    for j in jobs:
        if j["status"] == "complete":
            return j["id"]
    pytest.skip("no complete scan")


def _wait(sess, sid, timeout=120):
    t0 = time.time()
    d = None
    while time.time() - t0 < timeout:
        d = sess.get(f"{API}/gigs/{sid}", timeout=30).json()
        if d["status"] != "building":
            break
        time.sleep(3)
    return d, time.time() - t0


def test_01_pro_audit_start(pro):
    STATE["pro_job"] = _job(pro)
    before = pro.get(f"{API}/billing/me", timeout=30).json()
    STATE["scans_before"] = before.get("scans_used_this_month")
    t0 = time.time()
    r = pro.post(f"{API}/gigs/audit", json={"job_id": STATE["pro_job"], "original": ORIGINAL}, timeout=60)
    print("audit latency", time.time() - t0)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "audit" and d["status"] == "building"
    assert "audit" in d["pending_sections"] and len(d["pending_sections"]) == 9
    a = d["audit"]
    assert a["original"]["title"] == "do a logo for you"  # 'I will' stripped
    b = a["before"]
    secs = {c["section"] for c in b["checklist"]}
    assert secs <= {"titles", "tags", "description", "pricing", "faq"}
    assert "requirements" not in secs and "gallery" not in secs and "category" not in secs
    keys = {c["key"]: c["status"] for c in b["checklist"]}
    assert keys["desc_safe"] == "fail"
    assert keys["pricing"] == "pass"
    assert keys["faq"] == "fail"
    assert b["total"] == len(b["checklist"]) and b["passed"] == sum(c["status"] == "pass" for c in b["checklist"])
    print("before", b["passed"], "/", b["total"], keys)
    STATE["sid"] = d["id"]


def test_02_pro_audit_completes(pro):
    d, took = _wait(pro, STATE["sid"])
    print("completed in", took, "failed", d["failed_sections"])
    assert d["status"] == "complete"
    assert d["pending_sections"] == []
    for k in ["titles", "category", "tags", "pricing", "description", "faq", "requirements", "gallery"]:
        assert d["sections"][k], k
    issues = d["audit"]["issues"]
    assert issues and 5 <= len(issues) <= 8, issues
    for i in issues:
        assert i["severity"] in ("high", "medium", "low")
        assert i["section"] in ["titles", "category", "tags", "pricing", "description", "faq", "requirements", "gallery"]
        assert i["problem"] and i["fix"]
    assert d["score"]["total"] == 11
    print("after", d["score"], "issues", [i["problem"][:60] for i in issues])
    # rewritten desc must not contain off-platform
    assert "whatsapp" not in d["sections"]["description"].lower()
    STATE["setup"] = d


def test_03_quota_unchanged(pro):
    assert pro.get(f"{API}/billing/me", timeout=30).json().get("scans_used_this_month") == STATE["scans_before"]


def test_04_list_kind(pro):
    items = pro.get(f"{API}/gigs", timeout=30).json()["items"]
    me = next(i for i in items if i["id"] == STATE["sid"])
    assert me["kind"] == "audit"
    assert all(i["kind"] in ("audit", "build") for i in items)


def test_05_validation(pro, demo):
    r = pro.post(f"{API}/gigs/audit", json={"job_id": STATE["pro_job"], "original": {"title": "abc"}}, timeout=30)
    assert r.status_code == 422
    r = pro.post(f"{API}/gigs/audit", json={"job_id": str(uuid.uuid4()), "original": ORIGINAL}, timeout=30)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "SCAN_REQUIRED"
    # job owned by another user
    r = demo.post(f"{API}/gigs/audit", json={"job_id": STATE["pro_job"], "original": ORIGINAL}, timeout=30)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "SCAN_REQUIRED"
    r = pro.post(f"{API}/gigs/audit", json={"original": ORIGINAL}, timeout=30)
    assert r.status_code == 422


def test_06_title_only_audit_before(pro):
    r = pro.post(f"{API}/gigs/audit", json={"job_id": STATE["pro_job"],
                 "original": {"title": "  i will design minimalist logo design"}}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["audit"]["original"]["title"] == "design minimalist logo design"
    secs = {c["section"] for c in d["audit"]["before"]["checklist"]}
    assert secs == {"titles"}
    assert d["audit"]["before"]["passed"] == 2
    STATE["sid2"] = d["id"]


def test_07_free_audit(demo):
    jid = _job(demo)
    r = demo.post(f"{API}/gigs/audit", json={"job_id": jid, "original": ORIGINAL}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_pro"] is False and d["kind"] == "audit"
    assert sorted(d["pending_sections"]) == ["audit", "category", "tags", "titles"]
    STATE["fsid"] = d["id"]
    d, _ = _wait(demo, d["id"])
    assert d["status"] == "complete"
    assert 5 <= len(d["audit"]["issues"] or []) <= 8
    assert d["audit"]["before"]["total"] > 0
    for k in ["titles", "tags", "category"]:
        assert d["sections"][k]
    for k in ["description", "faq", "gallery", "pricing", "requirements"]:
        assert d["sections"][k] is None
    print("free before", d["audit"]["before"]["passed"], d["audit"]["before"]["total"], "after", d["score"])
    assert demo.get(f"{API}/gigs/{d['id']}/docx", timeout=30).status_code == 402


def test_08_build_regression(pro):
    r = pro.post(f"{API}/gigs/build", json={"job_id": STATE["pro_job"]}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "build" and d["audit"] is None
    assert "audit" not in d["pending_sections"]
    STATE["bsid"] = d["id"]
    d, _ = _wait(pro, d["id"])
    assert d["status"] == "complete" and d["kind"] == "build"


def test_09_cleanup(pro, demo):
    for sess, k in ((pro, "sid"), (pro, "sid2"), (pro, "bsid"), (demo, "fsid")):
        if STATE.get(k):
            if k == "sid2":
                _wait(sess, STATE[k])
            assert sess.delete(f"{API}/gigs/{STATE[k]}", timeout=30).status_code == 200
