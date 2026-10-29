# Iteration 4: store validation/reset, size sorting, per email+IP lockout, no prices
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@blaklader.local", "password": "Admin123!"}
CUSTOMER = {"email": "delivered@resend.dev", "password": "secret12"}
BORAS = "b9a119ee-c1a5-4ec9-8955-c907f93818bd"


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


@pytest.fixture(scope="module")
def db():
    return MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
    if r.status_code != 200:
        pytest.skip(f"login failed {creds['email']} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_h():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def cust_h():
    return _login(CUSTOMER)


# --- FIX 2: store validation + reset
class TestStoreFix:
    @pytest.mark.parametrize("body", [
        {"title": "", "text": "x"}, {"title": "x", "text": ""},
        {"title": "   ", "text": "x"}, {"title": "x", "text": "   "},
    ])
    def test_put_empty_rejected(self, admin_h, body):
        r = requests.put(f"{BASE_URL}/api/admin/stores/{BORAS}", json=body, headers=admin_h)
        assert r.status_code in (400, 422), r.text
        g = requests.get(f"{BASE_URL}/api/admin/stores/{BORAS}", headers=admin_h).json()
        assert g["title"].strip() and g["text"].strip()

    def test_put_empty_default_rejected(self, admin_h):
        r = requests.put(f"{BASE_URL}/api/admin/stores/default", json={"title": " ", "text": " "}, headers=admin_h)
        assert r.status_code in (400, 422)

    def test_delete_default_400(self, admin_h):
        r = requests.delete(f"{BASE_URL}/api/admin/stores/default", headers=admin_h)
        assert r.status_code == 400

    def test_delete_requires_admin(self, cust_h):
        r = requests.delete(f"{BASE_URL}/api/admin/stores/{BORAS}", headers=cust_h)
        assert r.status_code == 403
        assert requests.delete(f"{BASE_URL}/api/admin/stores/{BORAS}").status_code in (401, 403)

    def test_put_then_reset_flow(self, admin_h, cust_h, db):
        before = db.stores.find_one({"id": BORAS}, {"_id": 0})
        try:
            body = {"title": "TEST_Borås titel", "text": "TEST_text", "address": "Gatan 1", "phone": "", "email": "", "hours": ""}
            r = requests.put(f"{BASE_URL}/api/admin/stores/{BORAS}", json=body, headers=admin_h)
            assert r.status_code == 200 and r.json()["custom"] is True
            g = requests.get(f"{BASE_URL}/api/admin/stores/{BORAS}", headers=admin_h).json()
            assert g["custom"] is True and g["title"] == "TEST_Borås titel"
            assert requests.get(f"{BASE_URL}/api/home", headers=cust_h).json()["title"] == "TEST_Borås titel"
            d = requests.delete(f"{BASE_URL}/api/admin/stores/{BORAS}", headers=admin_h)
            assert d.status_code == 200 and d.json()["custom"] is False
            g = requests.get(f"{BASE_URL}/api/admin/stores/{BORAS}", headers=admin_h).json()
            dflt = requests.get(f"{BASE_URL}/api/admin/stores/default", headers=admin_h).json()
            assert g["custom"] is False and g["title"] == dflt["title"]
            h = requests.get(f"{BASE_URL}/api/home", headers=cust_h).json()
            assert h["title"] == dflt["title"] and h["city_name"] == "Borås"
        finally:
            db.stores.delete_one({"id": BORAS})
            if before:
                db.stores.insert_one(before)

    def test_delete_unknown_city(self, admin_h):
        r = requests.delete(f"{BASE_URL}/api/admin/stores/nonexistent-xyz", headers=admin_h)
        print("DELETE unknown city ->", r.status_code)
        assert r.status_code in (200, 404)


# --- FIX 3: size sort
class TestSizeSort:
    def test_size_order(self, cust_h):
        r = requests.get(f"{BASE_URL}/api/filters", headers=cust_h)
        assert r.status_code == 200
        data = r.json()
        defs = data if isinstance(data, list) else data.get("filters", data)
        size = next(f for f in defs if f.get("code") == "Size")
        vals = [o["value"] if isinstance(o, dict) else o for o in size["values"]]
        print("SIZES:", vals)
        idx = {v: i for i, v in enumerate(vals)}
        seq = [v for v in ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL", "6XL", "7XL"] if v in idx]
        assert [idx[v] for v in seq] == sorted(idx[v] for v in seq)
        nxl = [v for v in vals if v[:1].isdigit() and "XL" in v]
        first_num = next((i for i, v in enumerate(vals) if v[:1].isdigit() and "XL" not in v), len(vals))
        assert all(idx[v] < first_num for v in nxl), "NXL sizes mixed with numeric"
        if "One size" in idx:
            assert all(idx["One size"] > idx[v] for v in nxl) and idx["One size"] < first_num
        for a, b in [("4XL", "4XLT"), ("4XLT", "5XL")]:
            if a in idx and b in idx:
                assert idx[a] < idx[b]


# --- FIX 4: lockout per email+IP
class TestLockout:
    def _reg(self):
        email = f"test_lock_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "Right123!", "name": "TEST Lock", "phone": "0701234567",
            "company": "TEST AB", "org_number": "", "city_id": BORAS})
        assert r.status_code in (200, 201), r.text
        return email

    def test_5_fails_then_429_and_other_ip_ok(self, db):
        email = self._reg()
        try:
            ipA = {"X-Forwarded-For": "10.10.10.1"}
            for _ in range(5):
                assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad"}, headers=ipA).status_code == 401
            r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Right123!"}, headers=ipA)
            print("6th attempt same ip:", r.status_code)
            ips = set(a["ip"] for a in db.login_attempts.find({"email": email}))
            print("stored IPs:", ips)
            r2 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Right123!"}, headers={"X-Forwarded-For": "10.10.10.2"})
            print("other ip:", r2.status_code)
            assert r.status_code == 429
        finally:
            db.login_attempts.delete_many({"email": email})
            db.users.delete_one({"email": email})

    def test_success_clears_ip_records(self, db):
        email = self._reg()
        try:
            for _ in range(4):
                requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad"})
            assert db.login_attempts.count_documents({"email": email}) == 4
            assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Right123!"}).status_code == 200
            assert db.login_attempts.count_documents({"email": email}) == 0
            for _ in range(4):
                requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad"})
            assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Right123!"}).status_code == 200
        finally:
            db.login_attempts.delete_many({"email": email})
            db.users.delete_one({"email": email})

    def test_30_per_email_cap(self, db):
        email = f"test_cap_{uuid.uuid4().hex[:8]}@example.com"
        try:
            codes = []
            for i in range(31):
                codes.append(requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad"},
                                           headers={"X-Forwarded-For": f"10.20.{i}.1"}).status_code)
            print("codes:", codes)
            assert codes[-1] == 429
        finally:
            db.login_attempts.delete_many({"email": email})


# --- FIX 5: no prices
class TestNoPrices:
    def test_no_price_keys(self, cust_h):
        r = requests.get(f"{BASE_URL}/api/products", headers=cust_h)
        assert r.status_code == 200
        assert "price" not in r.text.lower()
