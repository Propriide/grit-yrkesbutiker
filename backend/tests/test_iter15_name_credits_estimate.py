# Iteration 15: user 'name' field (register/me/admin) + POST /api/credits/estimate
import math
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = uuid.uuid4().hex[:6]
CREATED = []


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def cities():
    return requests.get(f"{API}/cities").json()


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED:
        mdb.users.delete_one({"id": uid})
    mdb.users.delete_many({"email": {"$regex": f"t15{TAG}"}})
    mdb.companies.delete_many({"name": {"$regex": f"TEST_T15 {TAG}"}})


def reg_payload(cities, **kw):
    p = {"email": f"test+t15{TAG}{uuid.uuid4().hex[:4]}@example.com", "password": "secret12", "phone": "07011111",
         "company": f"TEST_T15 {TAG}", "name": "TEST Anna Andersson", "city_id": cities[0]["id"] if cities else None}
    p.update(kw)
    return p


@pytest.fixture(scope="module")
def customer(cities):
    r = requests.post(f"{API}/auth/register", json=reg_payload(cities))
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED.append(d["user"]["id"])
    return {"Authorization": f"Bearer {d['access_token']}"}, d["user"]


# --- name field: register / me ---
class TestName:
    def test_register_without_name_422(self, cities):
        p = reg_payload(cities)
        p.pop("name")
        r = requests.post(f"{API}/auth/register", json=p)
        assert r.status_code == 422

    def test_register_empty_name_422(self, cities):
        r = requests.post(f"{API}/auth/register", json=reg_payload(cities, name=""))
        assert r.status_code == 422

    def test_register_whitespace_name(self, cities):
        r = requests.post(f"{API}/auth/register", json=reg_payload(cities, name="   "))
        if r.status_code == 200:
            CREATED.append(r.json()["user"]["id"])
        print("whitespace-name register ->", r.status_code, r.json().get("user", {}).get("name") if r.ok else r.text)

    def test_register_returns_name_and_me(self, customer, cities):
        h, u = customer
        assert u["name"] == "TEST Anna Andersson"
        me = requests.get(f"{API}/auth/me", headers=h).json()
        assert me["name"] == "TEST Anna Andersson"
        assert me["city_id"] == cities[0]["id"]
        assert me["city_name"] == cities[0]["name"]

    def test_put_me_updates_name(self, customer):
        h, u = customer
        r = requests.put(f"{API}/auth/me", headers=h, json={"name": "  TEST Bertil  ", "phone": "07022222",
                                                           "company": u["company"], "org_number": "", "city_id": u["city_id"]})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST Bertil"
        assert requests.get(f"{API}/auth/me", headers=h).json()["name"] == "TEST Bertil"

    def test_admin_put_name(self, admin, customer):
        _, u = customer
        r = requests.put(f"{API}/admin/users/{u['id']}", headers=admin, json={"name": "TEST Admin Satt"})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST Admin Satt"
        g = requests.get(f"{API}/admin/users/{u['id']}", headers=admin).json()
        assert g["name"] == "TEST Admin Satt"

    def test_admin_create_with_name(self, admin, cities):
        r = requests.post(f"{API}/admin/users", headers=admin, json={
            "email": f"test+t15{TAG}adm@example.com", "password": "secret12", "phone": "0701", "name": "TEST Created",
            "company": f"TEST_T15 {TAG}", "city_id": cities[0]["id"] if cities else None})
        assert r.status_code == 200, r.text
        CREATED.append(r.json()["id"])
        assert r.json()["name"] == "TEST Created"
        g = requests.get(f"{API}/admin/users/{r.json()['id']}", headers=admin).json()
        assert g["name"] == "TEST Created"

    def test_patrik_name(self):
        h = login("patrik.degerstam@yp.se", "12345")
        assert requests.get(f"{API}/auth/me", headers=h).json()["name"] == "Patrik"


# --- credits estimate ---
class TestEstimate:
    def test_requires_auth(self):
        assert requests.post(f"{API}/credits/estimate", json={"items": []}).status_code == 401

    def test_disabled_returns_zero(self, admin, customer):
        h, u = customer
        requests.put(f"{API}/admin/users/{u['id']}", headers=admin, json={"credits_enabled": False})
        p = mdb.products.find_one({"price": {"$gt": 0}}, {"_id": 0, "part_no": 1})
        r = requests.post(f"{API}/credits/estimate", headers=h, json={"items": [{"part_no": p["part_no"], "quantity": 5}]})
        assert r.status_code == 200
        assert r.json() == {"enabled": False, "credits": 0}

    def test_enabled_calc_no_prices(self, admin, customer):
        h, u = customer
        assert requests.put(f"{API}/admin/users/{u['id']}", headers=admin, json={"credits_enabled": True}).status_code == 200
        cid = u["city_id"]
        prods = list(mdb.products.find({"price": {"$gt": 0}, "hidden_city_ids": {"$ne": cid}}, {"_id": 0, "part_no": 1, "price": 1}).limit(2))
        assert len(prods) == 2
        items = [{"part_no": prods[0]["part_no"], "quantity": 3}, {"part_no": prods[1]["part_no"], "quantity": 2}]
        r = requests.post(f"{API}/credits/estimate", headers=h, json={"items": items})
        assert r.status_code == 200
        d = r.json()
        expected = math.floor((prods[0]["price"] * 3 + prods[1]["price"] * 2) / 100)
        assert d == {"enabled": True, "credits": expected}, (d, expected, prods)
        assert "price" not in r.text.lower()

    def test_quantity_scales(self, customer):
        h, u = customer
        p = mdb.products.find_one({"price": {"$gt": 0}, "hidden_city_ids": {"$ne": u["city_id"]}}, {"_id": 0, "part_no": 1, "price": 1})
        c1 = requests.post(f"{API}/credits/estimate", headers=h, json={"items": [{"part_no": p["part_no"], "quantity": 1}]}).json()["credits"]
        c10 = requests.post(f"{API}/credits/estimate", headers=h, json={"items": [{"part_no": p["part_no"], "quantity": 10}]}).json()["credits"]
        assert c1 == math.floor(p["price"] / 100)
        assert c10 == math.floor(p["price"] * 10 / 100)

    def test_empty_and_unknown(self, customer):
        h, _ = customer
        assert requests.post(f"{API}/credits/estimate", headers=h, json={"items": []}).json() == {"enabled": True, "credits": 0}
        r = requests.post(f"{API}/credits/estimate", headers=h, json={"items": [{"part_no": "NOPE_XYZ", "quantity": 2}]})
        assert r.json() == {"enabled": True, "credits": 0}

    def test_invalid_quantity_422(self, customer):
        h, _ = customer
        for q in (0, 1000):
            r = requests.post(f"{API}/credits/estimate", headers=h, json={"items": [{"part_no": "X", "quantity": q}]})
            assert r.status_code == 422

    def test_hidden_product_excluded(self, customer):
        h, u = customer
        p = mdb.products.find_one({"price": {"$gt": 0}, "hidden_city_ids": u["city_id"]}, {"_id": 0, "part_no": 1})
        if not p:
            pytest.skip("no hidden product for city")
        r = requests.post(f"{API}/credits/estimate", headers=h, json={"items": [{"part_no": p["part_no"], "quantity": 5}]})
        assert r.json()["credits"] == 0
