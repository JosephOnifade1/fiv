"""Iteration 4 — Referral tests (/api/referral/code, /api/referral/redeem)."""
import os
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


def _admin_token():
    return jwt.encode(
        {"sub": ADMIN_SUB, "email": ADMIN_EMAIL,
         "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
        JWT_SECRET, algorithm="HS256",
    )


def _make_user():
    email = f"TEST_ref_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Testpass123!", "name": "RefT"})
    assert r.status_code == 200, r.text
    return email, r.json()["token"]


def _client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture
def user_a():
    email, token = _make_user()
    c = _client(token); c.email = email
    return c


@pytest.fixture
def user_b():
    email, token = _make_user()
    c = _client(token); c.email = email
    return c


class TestReferralCode:
    def test_get_code_shape(self, user_a):
        r = user_a.get(f"{API}/referral/code")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["code"].startswith("FS-")
        assert "share_url" in d and d["share_url"].startswith("/?ref=")
        assert isinstance(d["redemptions"], int)
        assert "reward" in d

    def test_code_is_deterministic(self, user_a):
        c1 = user_a.get(f"{API}/referral/code").json()["code"]
        c2 = user_a.get(f"{API}/referral/code").json()["code"]
        assert c1 == c2


class TestReferralRedeem:
    def test_self_redeem_400(self, user_a):
        my_code = user_a.get(f"{API}/referral/code").json()["code"]
        r = user_a.post(f"{API}/referral/redeem", json={"code": my_code})
        assert r.status_code == 400, r.text

    def test_invalid_code_404(self, user_a):
        r = user_a.post(f"{API}/referral/redeem", json={"code": "FS-XXNOEXIST"})
        assert r.status_code == 404, r.text

    def test_redeem_success_grants_30_days(self, user_a, user_b):
        ref_code = user_a.get(f"{API}/referral/code").json()["code"]
        r = user_b.post(f"{API}/referral/redeem", json={"code": ref_code})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["granted_days"] == 30
        assert "new_plan_expires_at" in d
        # Verify b is now pro
        me_b = user_b.get(f"{API}/billing/me").json()
        assert me_b["plan"] == "pro"
        # Verify a is now pro too (referrer reward)
        me_a = user_a.get(f"{API}/billing/me").json()
        assert me_a["plan"] == "pro"

    def test_double_redeem_400(self, user_a, user_b):
        ref_code = user_a.get(f"{API}/referral/code").json()["code"]
        r1 = user_b.post(f"{API}/referral/redeem", json={"code": ref_code})
        assert r1.status_code == 200
        r2 = user_b.post(f"{API}/referral/redeem", json={"code": ref_code})
        assert r2.status_code == 400, r2.text
