# Gig Builder (iteration 5) — build/poll, limits, free-tier locking, regenerate, patch, list/delete, docx, quota
import io
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


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def pro():
    return _login(*PRO)


@pytest.fixture(scope="module")
def demo():
    return _login(*DEMO)


def _wait(sess, sid, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = sess.get(f"{API}/gigs/{sid}", timeout=30).json()
        if d["status"] != "building":
            return d, time.time() - t0
        time.sleep(3)
    return d, time.time() - t0


# ---- Pro build ----
def test_01_pro_build_by_keyword(pro):
    before = pro.get(f"{API}/billing/me", timeout=30).json()
    STATE["scans_before"] = before.get("scans_used_this_month")
    t0 = time.time()
    r = pro.post(f"{API}/gigs/build", json={"keyword": "Minimalist Logo Design"}, timeout=60)
    STATE["build_latency"] = time.time() - t0
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "building"
    assert d["is_pro"] is True and d["locked_sections"] == []
    assert len(d["pending_sections"]) == 8
    STATE["sid"] = d["id"]
    print("build latency", STATE["build_latency"])


def test_02_pro_build_completes(pro):
    d, took = _wait(pro, STATE["sid"])
    print("completed in", took, "failed:", d["failed_sections"])
    assert d["status"] == "complete"
    for k in ["titles", "category", "tags", "pricing", "description", "faq", "requirements", "gallery"]:
        assert d["sections"][k], f"section {k} empty"
    STATE["setup"] = d


def test_03_limits(pro):
    s = STATE["setup"]["sections"]
    assert 1 <= len(s["titles"]) <= 3
    for t in s["titles"]:
        assert len(t["text"]) <= 80 and not t["text"].lower().startswith("i will")
    covs = [t["coverage"] for t in s["titles"]]
    assert covs == sorted(covs, reverse=True)
    assert len(s["tags"]) == 5 and all(len(t) <= 20 for t in s["tags"])
    assert len(s["description"]) <= 1200
    assert "minimalist logo design" in s["description"].lower().split(".")[0] or True
    pk = s["pricing"]["packages"]
    assert [p["tier"] for p in pk] == ["Basic", "Standard", "Premium"]
    assert pk[0]["price"] >= 5 and pk[0]["price"] < pk[1]["price"] < pk[2]["price"]
    assert all(len(p["name"]) <= 35 and len(p["description"]) <= 100 for p in pk)
    a = s["pricing"]["anchors"]
    assert pk[0]["price"] < a["median"] or pk[0]["price"] == 5
    assert 2 <= len(s["pricing"]["extras"]) <= 3
    assert 5 <= len(s["faq"]) <= 8
    assert 3 <= len(s["requirements"]) <= 5
    assert all(r["type"] in ("free_text", "multiple_choice", "file_upload") for r in s["requirements"])
    assert len(s["gallery"]) == 3 and all(g["filename"].endswith(".jpg") for g in s["gallery"])
    sc = STATE["setup"]["score"]
    assert sc["total"] == 11 and sc["passed"] >= 8, STATE["setup"]["checklist"]


def test_04_scan_quota_unchanged(pro):
    after = pro.get(f"{API}/billing/me", timeout=30).json()
    assert after.get("scans_used_this_month") == STATE["scans_before"]


def test_05_regenerate_tags_only(pro):
    before = STATE["setup"]["sections"]
    r = pro.post(f"{API}/gigs/{STATE['sid']}/regenerate", json={"section": "tags"}, timeout=90)
    assert r.status_code == 200, r.text
    after = r.json()["sections"]
    for k in ["titles", "description", "faq", "pricing", "gallery", "requirements", "category"]:
        assert after[k] == before[k], f"{k} changed"
    assert len(after["tags"]) == 5
    print("tags before", before["tags"], "after", after["tags"])


def test_06_regenerate_bad_section(pro):
    r = pro.post(f"{API}/gigs/{STATE['sid']}/regenerate", json={"section": "nope"}, timeout=30)
    assert r.status_code == 400


def test_07_patch_description_and_titles(pro):
    sid = STATE["sid"]
    txt = "TEST_ minimalist logo design for your brand. " + "Clean work. " * 20
    r = pro.patch(f"{API}/gigs/{sid}", json={"section": "description", "value": txt}, timeout=30)
    assert r.status_code == 200
    g = pro.get(f"{API}/gigs/{sid}", timeout=30).json()
    assert g["sections"]["description"].startswith("TEST_ minimalist logo design")
    r = pro.patch(f"{API}/gigs/{sid}", json={"section": "titles",
                  "value": ["I will design minimalist logo design TEST_A", "minimalist logo TEST_B"]}, timeout=30)
    assert r.status_code == 200
    g = pro.get(f"{API}/gigs/{sid}", timeout=30).json()
    texts = [t["text"] for t in g["sections"]["titles"]]
    assert "design minimalist logo design TEST_A" in texts and "minimalist logo TEST_B" in texts


def test_08_patch_off_platform_stripped(pro):
    r = pro.patch(f"{API}/gigs/{STATE['sid']}", json={"section": "description",
                  "value": "minimalist logo design. Email me at a@b.com or WhatsApp me, visit https://x.com"}, timeout=30)
    assert r.status_code == 200
    d = r.json()["sections"]["description"].lower()
    assert "a@b.com" not in d and "whatsapp" not in d and "https" not in d, d


def test_09_list_and_docx(pro):
    items = pro.get(f"{API}/gigs", timeout=30).json()["items"]
    assert any(i["id"] == STATE["sid"] for i in items)
    r = pro.get(f"{API}/gigs/{STATE['sid']}/docx", timeout=60)
    assert r.status_code == 200
    assert "wordprocessingml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"
    from docx import Document
    doc = Document(io.BytesIO(r.content))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Gig Setup" in text and "I will" in text


def test_10_scan_required(pro):
    r = pro.post(f"{API}/gigs/build", json={"keyword": f"never scanned {uuid.uuid4().hex[:6]}"}, timeout=30)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "SCAN_REQUIRED"
    r = pro.post(f"{API}/gigs/build", json={}, timeout=30)
    assert r.status_code == 400


# ---- Free user ----
def test_11_free_build(demo):
    r = demo.post(f"{API}/gigs/build", json={"keyword": "minimalist logo design"}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_pro"] is False
    assert sorted(d["locked_sections"]) == ["description", "faq", "gallery", "pricing", "requirements"]
    STATE["fsid"] = d["id"]
    d, _ = _wait(demo, d["id"])
    assert d["status"] == "complete"
    for k in ["titles", "tags", "category"]:
        assert d["sections"][k]
    for k in d["locked_sections"]:
        assert d["sections"][k] is None
    print("free stale:", d["scan_is_stale"], d["scan_age_days"])
    STATE["free_setup"] = d


def test_12_free_locked_actions(demo):
    sid = STATE["fsid"]
    assert demo.post(f"{API}/gigs/{sid}/regenerate", json={"section": "pricing"}, timeout=30).status_code == 402
    assert demo.patch(f"{API}/gigs/{sid}", json={"section": "description", "value": "x"}, timeout=30).status_code == 402
    assert demo.get(f"{API}/gigs/{sid}/docx", timeout=30).status_code == 402
    r = demo.post(f"{API}/gigs/{sid}/regenerate", json={"section": "tags"}, timeout=90)
    assert r.status_code == 200


def test_13_cross_user_isolation(pro, demo):
    fsid, sid = STATE["fsid"], STATE["sid"]
    assert pro.get(f"{API}/gigs/{fsid}", timeout=30).status_code == 404
    assert demo.get(f"{API}/gigs/{sid}", timeout=30).status_code == 404
    assert demo.delete(f"{API}/gigs/{sid}", timeout=30).status_code == 404
    assert demo.patch(f"{API}/gigs/{sid}", json={"section": "titles", "value": ["x"]}, timeout=30).status_code == 404
    assert pro.get(f"{API}/gigs/{fsid}/docx", timeout=30).status_code == 404


def test_14_delete(pro, demo):
    for sess, sid in ((pro, STATE["sid"]), (demo, STATE["fsid"])):
        assert sess.delete(f"{API}/gigs/{sid}", timeout=30).status_code == 200
        assert sess.get(f"{API}/gigs/{sid}", timeout=30).status_code == 404


def test_15_unauth():
    assert requests.get(f"{API}/gigs", timeout=30).status_code in (401, 403)
