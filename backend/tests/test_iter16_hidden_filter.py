# Iteration 16: GET /api/products?hidden_in=any|<city_id> admin-only hidden-articles filter
import os

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def all_items(headers, **params):
    out, page = [], 1
    while True:
        r = requests.get(f"{API}/products", headers=headers, params={**params, "page": page, "page_size": 60})
        assert r.status_code == 200, r.text
        d = r.json()
        out += d["items"]
        if not d["has_more"]:
            return out, d["total"]
        page += 1


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def patrik():
    return login("patrik.degerstam@yp.se", "12345")


@pytest.fixture(scope="module")
def customer():
    return login("delivered@resend.dev", "secret12")


@pytest.fixture(scope="module")
def cities():
    return {c["name"]: c["id"] for c in requests.get(f"{API}/cities").json()}


def db_hidden(city_id=None):
    q = {"active": {"$ne": False}, "hidden_city_ids": city_id if city_id else {"$exists": True, "$ne": []}}
    return {p["part_no"] for p in mdb.products.find(q, {"_id": 0, "part_no": 1})}


# --- admin: hidden_in=any
class TestHiddenAny:
    def test_any_returns_only_hidden(self, admin):
        items, total = all_items(admin, hidden_in="any")
        expected = db_hidden()
        assert expected, "precondition: some hidden products"
        assert {i["part_no"] for i in items} == expected
        assert total == len(expected)
        assert all(i.get("hidden_city_ids") for i in items)

    def test_any_patrik_admin(self, patrik):
        items, _ = all_items(patrik, hidden_in="any")
        assert {i["part_no"] for i in items} == db_hidden()

    def test_no_filter_returns_full_catalog(self, admin):
        r = requests.get(f"{API}/products", headers=admin, params={"page_size": 1})
        assert r.json()["total"] > len(db_hidden())


# --- admin: hidden_in=<city_id>
class TestHiddenCity:
    def test_each_city(self, admin, cities):
        for name, cid in cities.items():
            items, total = all_items(admin, hidden_in=cid)
            expected = db_hidden(cid)
            assert {i["part_no"] for i in items} == expected, name
            assert total == len(expected)
            assert all(cid in i["hidden_city_ids"] for i in items)

    def test_two_city_product_in_both(self, admin, cities):
        p = mdb.products.find_one({"hidden_city_ids.1": {"$exists": True}}, {"_id": 0})
        if not p:
            pytest.skip("no product hidden in 2 cities")
        for cid in p["hidden_city_ids"]:
            items, _ = all_items(admin, hidden_in=cid)
            assert p["part_no"] in {i["part_no"] for i in items}

    def test_unknown_city_empty(self, admin):
        r = requests.get(f"{API}/products", headers=admin, params={"hidden_in": "nope-city"})
        assert r.status_code == 200 and r.json()["total"] == 0

    def test_combined_with_search(self, admin, cities):
        r = requests.get(f"{API}/products", headers=admin, params={"hidden_in": "any", "q": "17211645"})
        d = r.json()
        assert [i["part_no"] for i in d["items"]] == ["17211645"]


# --- customer: hidden_in ignored
class TestCustomerIgnored:
    def test_customer_hidden_in_ignored(self, customer, cities):
        base = requests.get(f"{API}/products", headers=customer, params={"page_size": 1}).json()["total"]
        for v in ["any", cities["Borås"], cities["Göteborg"]]:
            d = requests.get(f"{API}/products", headers=customer, params={"hidden_in": v, "page_size": 60}).json()
            assert d["total"] == base, v
            assert all("hidden_city_ids" not in i for i in d["items"])

    def test_customer_never_sees_own_city_hidden(self, customer, cities):
        items, _ = all_items(customer, hidden_in="any", q="1")
        assert not ({i["part_no"] for i in items} & db_hidden(cities["Borås"]))

    def test_unauth_401(self):
        assert requests.get(f"{API}/products", params={"hidden_in": "any"}).status_code == 401


# --- product detail sizes (used by cart size sheet)
class TestProductSizes:
    def test_product_detail_has_sizes(self, customer):
        r = requests.get(f"{API}/products/44062513", headers=customer)
        assert r.status_code == 200
        assert isinstance(r.json()["sizes"], list) and len(r.json()["sizes"]) > 1
