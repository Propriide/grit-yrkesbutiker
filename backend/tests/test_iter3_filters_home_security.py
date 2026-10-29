# Iteration 3: no prices, Blåkläder filter panel, home/store start page, login lockout, confirm-link host allowlist
import json
import os
import subprocess
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@blaklader.local", "password": "Admin123!"}
CUSTOMER = {"email": "delivered@resend.dev", "password": "secret12"}
FILTER_ORDER = ["FilterFunction", "FilterCollections", "FilterTypeOfGarment", "Size", "Color", "FilterCertification",
                "FilterHighvisClassification", "FilterHighVisCoCertification", "FilterMaterial", "P6412",
                "FilterFlameResistantCollection", "FilterMiljomarkning"]
LETTERS = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL"]


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
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


@pytest.fixture(scope="module")
def cust():
    return _login(CUSTOMER)


@pytest.fixture(scope="module")
def admin_h():
    return _login(ADMIN)[0]


def _products(h, **params):
    r = requests.get(f"{BASE_URL}/api/products", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ---- prices
class TestNoPrices:
    def test_list_has_no_price(self, cust):
        d = _products(cust[0], page_size=60)
        assert d["items"]
        assert "price" not in json.dumps(d["items"]).lower()

    def test_detail_has_no_price(self, cust):
        part = _products(cust[0])["items"][0]["part_no"]
        r = requests.get(f"{BASE_URL}/api/products/{part}", headers=cust[0])
        assert r.status_code == 200
        assert "price" not in r.json()
        assert '"price' not in json.dumps(r.json()).lower()


# ---- filters
class TestFilters:
    def test_filter_defs_order_and_counts(self, cust):
        r = requests.get(f"{BASE_URL}/api/filters", headers=cust[0])
        assert r.status_code == 200
        codes = [f["code"] for f in r.json()]
        print("codes", codes)
        assert all(c in FILTER_ORDER for c in codes)
        assert codes == sorted(codes, key=FILTER_ORDER.index)
        assert len(codes) >= 8
        for f in r.json():
            assert f["name"] and f["values"]
            assert all(isinstance(v["count"], int) and v["count"] > 0 for v in f["values"])

    def test_size_sorted(self, cust):
        f = {x["code"]: x for x in requests.get(f"{BASE_URL}/api/filters", headers=cust[0]).json()}
        sizes = [v["value"] for v in f["Size"]["values"]]
        letters = [s for s in sizes if s in LETTERS]
        assert letters == sorted(letters, key=LETTERS.index)
        first_num = next((i for i, s in enumerate(sizes) if s[:1].isdigit() and "XL" not in s), None)
        if first_num is not None:
            assert all(s not in LETTERS for s in sizes[first_num:]), sizes[:40]

    def test_filters_scoped_by_group(self, cust):
        all_f = {x["code"]: x for x in requests.get(f"{BASE_URL}/api/filters", headers=cust[0]).json()}
        g = {x["code"]: x for x in requests.get(f"{BASE_URL}/api/filters", headers=cust[0], params={"group": "underdelar"}).json()}
        assert sum(v["count"] for v in g["Color"]["values"]) < sum(v["count"] for v in all_f["Color"]["values"])

    def test_filter_or_within_and_across(self, cust):
        h = cust[0]
        f = {x["code"]: x for x in requests.get(f"{BASE_URL}/api/filters", headers=h, params={"group": "underdelar"}).json()}
        c1, c2 = f["Color"]["values"][0], f["Color"]["values"][1]
        base = {"group": "underdelar"}
        n1 = _products(h, **base, filters=json.dumps({"Color": [c1["value"]]}))["total"]
        n2 = _products(h, **base, filters=json.dumps({"Color": [c2["value"]]}))["total"]
        n12 = _products(h, **base, filters=json.dumps({"Color": [c1["value"], c2["value"]]}))["total"]
        assert n1 == c1["count"]
        assert max(n1, n2) <= n12 <= n1 + n2
        size = f["Size"]["values"][0]["value"]
        nand = _products(h, **base, filters=json.dumps({"Color": [c1["value"]], "Size": [size]}))["total"]
        assert nand <= n1
        total = _products(h, **base)["total"]
        assert n1 < total

    def test_filter_with_q(self, cust):
        h = cust[0]
        n = _products(h, q="byxa", filters=json.dumps({"Size": ["C50"]}))
        for it in n["items"]:
            assert "C50" in it.get("sizes", [])

    def test_invalid_json_400(self, cust):
        r = requests.get(f"{BASE_URL}/api/products", headers=cust[0], params={"filters": "{bad"})
        assert r.status_code == 400
        r = requests.get(f"{BASE_URL}/api/products", headers=cust[0], params={"filters": "[1,2]"})
        assert r.status_code == 400

    def test_unknown_code_ignored(self, cust):
        total = _products(cust[0])["total"]
        assert _products(cust[0], filters=json.dumps({"Bogus": ["x"]}))["total"] == total


# ---- home & stores
class TestHomeStores:
    def test_home_customer(self, cust):
        r = requests.get(f"{BASE_URL}/api/home", headers=cust[0])
        assert r.status_code == 200
        d = r.json()
        assert d["city_name"] == "Borås"
        for k in ("title", "text", "address", "phone", "email", "hours"):
            assert k in d

    def test_home_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/home").status_code in (401, 403)

    def test_admin_store_permissions(self, cust, admin_h):
        assert requests.get(f"{BASE_URL}/api/admin/stores/default", headers=cust[0]).status_code == 403
        assert requests.put(f"{BASE_URL}/api/admin/stores/default", headers=cust[0], json={"title": "x"}).status_code == 403
        assert requests.get(f"{BASE_URL}/api/admin/stores/nonexistent-city", headers=admin_h).status_code == 404
        assert requests.put(f"{BASE_URL}/api/admin/stores/nonexistent-city", headers=admin_h, json={"title": "x", "text": "y"}).status_code == 404

    def test_city_store_put_reflects_in_home(self, cust, admin_h, db):
        city_id = cust[1].get("city_id")
        assert city_id
        orig = db.stores.find_one({"id": city_id}, {"_id": 0})
        try:
            body = {"title": "TEST_Borås butik", "text": "TEST_text", "address": "Gatan 1", "phone": "033-1",
                    "email": "b@yp.se", "hours": "8-17"}
            r = requests.put(f"{BASE_URL}/api/admin/stores/{city_id}", headers=admin_h, json=body)
            assert r.status_code == 200 and r.json()["custom"] is True
            g = requests.get(f"{BASE_URL}/api/admin/stores/{city_id}", headers=admin_h).json()
            assert g["title"] == body["title"] and g["custom"] is True
            h = requests.get(f"{BASE_URL}/api/home", headers=cust[0]).json()
            assert h["title"] == body["title"] and h["text"] == "TEST_text" and h["hours"] == "8-17"
        finally:
            if orig:
                db.stores.replace_one({"id": city_id}, orig)
            else:
                db.stores.delete_one({"id": city_id})

    def test_default_store_fallback(self, cust, admin_h, db):
        city_id = cust[1].get("city_id")
        if db.stores.find_one({"id": city_id}):
            pytest.skip("city has custom store")
        orig = db.stores.find_one({"id": "default"}, {"_id": 0})
        try:
            r = requests.put(f"{BASE_URL}/api/admin/stores/default", headers=admin_h,
                             json={"title": "TEST_default", "text": "TEST_dtext"})
            assert r.status_code == 200
            h = requests.get(f"{BASE_URL}/api/home", headers=cust[0]).json()
            assert h["title"] == "TEST_default" and h["city_name"] == "Borås"
            other = requests.get(f"{BASE_URL}/api/cities").json()
            oid = next(c["id"] for c in other if c["id"] != city_id)
            g = requests.get(f"{BASE_URL}/api/admin/stores/{oid}", headers=admin_h).json()
            if not g["custom"]:
                assert g["title"] == "TEST_default"
        finally:
            if orig:
                db.stores.replace_one({"id": "default"}, orig)
            else:
                db.stores.delete_one({"id": "default"})

    def test_store_validation(self, admin_h):
        r = requests.put(f"{BASE_URL}/api/admin/stores/default", headers=admin_h, json={"title": "x" * 200})
        assert r.status_code == 422


# ---- login lockout
class TestLockout:
    def test_lockout_after_5_failures(self, db):
        cities = requests.get(f"{BASE_URL}/api/cities").json()
        email = f"test_lock_{uuid.uuid4().hex[:8]}@example.com"
        pw = "Secret123!"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": pw, "phone": "0701234567", "company": "TEST_Lock AB",
            "org_number": "", "city_id": cities[0]["id"] if cities else None})
        assert r.status_code == 200, r.text
        try:
            for i in range(5):
                rr = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "wrong"})
                assert rr.status_code == 401, (i, rr.status_code)
            rr = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
            assert rr.status_code == 429, rr.text
            rr = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email.upper(), "password": pw})
            assert rr.status_code == 429
        finally:
            db.users.delete_one({"email": email})
            db.login_attempts.delete_many({"email": email})

    def test_success_resets_counter(self, db):
        cities = requests.get(f"{BASE_URL}/api/cities").json()
        email = f"test_reset_{uuid.uuid4().hex[:8]}@example.com"
        pw = "Secret123!"
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": pw, "phone": "0701234567", "company": "TEST_Reset AB",
            "org_number": "", "city_id": cities[0]["id"] if cities else None})
        try:
            for _ in range(4):
                requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "wrong"})
            assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}).status_code == 200
            for _ in range(4):
                requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "wrong"})
            assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}).status_code == 200
        finally:
            db.users.delete_one({"email": email})
            db.login_attempts.delete_many({"email": email})


# ---- checkout regression + confirm-link host allowlist (sends one email)
class TestOrderHost:
    def test_order_with_evil_forwarded_host(self, cust, db):
        h = cust[0]
        p = _products(h, page_size=5)["items"][0]
        item = {"part_no": p["part_no"], "size": (p.get("sizes") or [""])[0], "quantity": 1,
                "color_code": (p.get("colors") or [{}])[0].get("code")}
        r = requests.post(f"{BASE_URL}/api/orders", headers={**h, "X-Forwarded-Host": "evil.example.com"},
                          json={"items": [item], "comment": "TEST_iter3 order"})
        assert r.status_code == 200, r.text
        d = r.json()
        print("email_status", d["email_status"], d["order_number"])
        assert "confirm_token" not in d and "sent_to" not in d
        assert db.orders.find_one({"id": d["id"]})
        time.sleep(1)
        log = subprocess.run("grep -h 'Order confirm link base' /var/log/supervisor/backend.*.log | tail -n 3",
                             shell=True, capture_output=True, text=True).stdout
        print(log)
        last = log.strip().splitlines()[-1]
        assert "evil.example.com" not in last
        assert "emergentagent.com" in last or "emergent.host" in last
        lst = requests.get(f"{BASE_URL}/api/orders", headers=h).json()
        assert lst[0]["id"] == d["id"]
