# Iteration 12: delivery choice, price hiding, credits, company credits, broadcast, per-city visibility, purchase ranking
# Order email recipient is temporarily switched to delivered@resend.dev (restored on teardown). Customers use delivered+tag@resend.dev.
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = uuid.uuid4().hex[:6]
COMPANY = f"TEST_Credit Bygg {TAG}"
API = f"{BASE_URL}/api"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def no_price(obj):
    s = json.dumps(obj)
    return '"price"' not in s and '"order_value"' not in s


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def cities():
    return requests.get(f"{API}/cities").json()


@pytest.fixture(scope="module", autouse=True)
def env_setup():
    old = mdb.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    mdb.settings.update_one({"id": "global"}, {"$set": {"order_email": "delivered@resend.dev"}}, upsert=True)
    hidden_snapshot = {p["part_no"]: p["hidden_city_ids"] for p in mdb.products.find({"hidden_city_ids": {"$exists": True, "$ne": []}}, {"_id": 0, "part_no": 1, "hidden_city_ids": 1})}
    yield
    mdb.settings.update_one({"id": "global"}, {"$set": {"order_email": old.get("order_email")}})
    ids = [u["id"] for u in mdb.users.find({"company": {"$regex": f"^TEST_Credit Bygg {TAG}", "$options": "i"}})]
    mdb.orders.delete_many({"user_id": {"$in": ids}})
    mdb.credit_tx.delete_many({"user_id": {"$in": ids}})
    mdb.notifications.delete_many({"user_id": {"$in": ids}})
    mdb.users.delete_many({"id": {"$in": ids}})
    mdb.companies.delete_many({"key": {"$regex": TAG}})
    mdb.broadcasts.delete_many({"title": {"$regex": "TEST_"}})
    mdb.notifications.delete_many({"title": {"$regex": "TEST_"}})
    # restore pre-existing visibility (do not wipe admin-hidden products)
    mdb.products.update_many({"hidden_city_ids": {"$exists": True, "$ne": []}, "part_no": {"$nin": list(hidden_snapshot)}}, {"$set": {"hidden_city_ids": []}})
    for pn, ids in hidden_snapshot.items():
        mdb.products.update_one({"part_no": pn}, {"$set": {"hidden_city_ids": ids}})


def register(cities, idx=0, company=COMPANY, n=None):
    r = requests.post(f"{API}/auth/register", json={
        "email": f"delivered+t{TAG}{n or uuid.uuid4().hex[:4]}@resend.dev", "password": "secret12", "phone": "07011111", "name": "TEST Namn",
        "company": company, "city_id": cities[idx]["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"Authorization": f"Bearer {d['access_token']}"}, d["user"]


@pytest.fixture(scope="module")
def cust(cities):
    return register(cities, 0, n="a")


@pytest.fixture(scope="module")
def product():
    return mdb.products.find_one({"price": {"$gt": 1000}, "sizes.0": {"$exists": True}, "colors.0": {"$exists": True}}, {"_id": 0})


# ---------- Delivery ----------
class TestDelivery:
    def test_missing_delivery_422(self, cust, product):
        r = requests.post(f"{API}/orders", headers=cust[0], json={"items": [{"part_no": product["part_no"], "size": product["sizes"][0], "quantity": 1}]})
        assert r.status_code in (400, 422)

    def test_invalid_method_400(self, cust, product):
        r = requests.post(f"{API}/orders", headers=cust[0], json={"items": [{"part_no": product["part_no"], "size": product["sizes"][0], "quantity": 1}],
                                                                  "delivery": {"method": "drone"}})
        assert r.status_code == 400

    def test_ship_without_address_400(self, cust, product):
        r = requests.post(f"{API}/orders", headers=cust[0], json={"items": [{"part_no": product["part_no"], "size": product["sizes"][0], "quantity": 1}],
                                                                  "delivery": {"method": "ship", "address": "Gatan 1", "postal_code": "", "city": "Borås"}})
        assert r.status_code == 400

    def test_ship_order_created_no_price(self, cust, product):
        r = requests.post(f"{API}/orders", headers=cust[0], json={
            "items": [{"part_no": product["part_no"], "size": product["sizes"][0], "color_code": product["colors"][0]["code"], "quantity": 2}],
            "delivery": {"method": "ship", "name": "Kalle", "address": "Gatan 1", "postal_code": "50330", "city": "Borås"}})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["delivery"] == {"method": "ship", "name": "Kalle", "address": "Gatan 1", "postal_code": "50330", "city": "Borås"}
        assert no_price(o)
        db_o = mdb.orders.find_one({"id": o["id"]})
        assert db_o["order_value"] == round(product["price"] * 2, 2)
        lst = requests.get(f"{API}/orders", headers=cust[0]).json()
        assert lst[0]["id"] == o["id"] and no_price(lst)
        one = requests.get(f"{API}/orders/{o['id']}", headers=cust[0]).json()
        assert one["delivery"]["method"] == "ship" and no_price(one)


# ---------- Prices hidden ----------
class TestPrices:
    def test_products_no_price(self, cust, admin, product):
        for h in (cust[0], admin):
            r = requests.get(f"{API}/products", headers=h, params={"page_size": 60})
            assert r.status_code == 200 and no_price(r.json())
            r = requests.get(f"{API}/products/{product['part_no']}", headers=h)
            assert r.status_code == 200 and no_price(r.json())


# ---------- Credits ----------
class TestCredits:
    def _insert_order(self, user, value, status="new"):
        oid = str(uuid.uuid4())
        mdb.orders.insert_one({"id": oid, "order_number": f"TEST{TAG}{oid[:4]}", "user_id": user["id"],
                               "customer": {"email": user["email"], "company": COMPANY}, "items": [], "comment": "",
                               "delivery": {"method": "store"}, "order_value": value, "status": status, "replies": [],
                               "created_at": datetime.now(timezone.utc).isoformat(), "confirm_token": uuid.uuid4().hex})
        return oid

    def test_credits_disabled_default(self, cities):
        h, u = register(cities, 1, company=f"TEST_Credit Bygg {TAG} solo")
        r = requests.get(f"{API}/credits", headers=h).json()
        assert r == {"enabled": False, "balance": 0, "history": []}

    def test_enable_confirm_award_once_and_decline(self, admin, cities):
        h, u = register(cities, 1, company=f"TEST_Credit Bygg {TAG} conf")
        r = requests.put(f"{API}/admin/users/{u['id']}", headers=admin, json={"credits_enabled": True})
        assert r.status_code == 200 and r.json()["credits_enabled"] is True
        c = requests.get(f"{API}/credits", headers=h).json()
        assert c["enabled"] is True and c["balance"] == 0
        oid = self._insert_order(u, 1234.5)
        r = requests.post(f"{API}/admin/orders/{oid}/reply", headers=admin, json={"message": "Klar fredag", "action": "confirm"})
        if r.status_code == 400:
            pytest.skip(f"reply email failed: {r.text}")
        assert r.status_code == 200, r.text
        assert r.json()["credits_earned"] == 12 and r.json()["status"] == "confirmed"
        c = requests.get(f"{API}/credits", headers=h).json()
        assert c["balance"] == 12 and c["history"][0]["amount"] == 12 and c["history"][0]["reason"] == "order"
        r = requests.post(f"{API}/admin/orders/{oid}/reply", headers=admin, json={"message": "Igen", "action": "confirm"})
        assert r.status_code in (200, 400)
        assert requests.get(f"{API}/credits", headers=h).json()["balance"] == 12
        oid2 = self._insert_order(u, 5000)
        r = requests.post(f"{API}/admin/orders/{oid2}/reply", headers=admin, json={"message": "Nej tyvärr", "action": "decline"})
        assert r.status_code in (200, 400)
        assert requests.get(f"{API}/credits", headers=h).json()["balance"] == 12
        assert "credits_earned" not in mdb.orders.find_one({"id": oid2})

    def test_admin_adjust_credits(self, admin, cities):
        h, u = register(cities, 1, company=f"TEST_Credit Bygg {TAG} adj")
        requests.put(f"{API}/admin/users/{u['id']}", headers=admin, json={"credits_enabled": True})
        r = requests.post(f"{API}/admin/users/{u['id']}/credits", headers=admin, json={"amount": 50, "note": "Bonus"})
        assert r.status_code == 200 and r.json()["credits"] == 50
        r = requests.post(f"{API}/admin/users/{u['id']}/credits", headers=admin, json={"amount": -60, "note": "x"})
        assert r.status_code == 400
        r = requests.post(f"{API}/admin/users/{u['id']}/credits", headers=admin, json={"amount": -20, "note": "Rättelse"})
        assert r.status_code == 200 and r.json()["credits"] == 30
        r = requests.post(f"{API}/admin/users/{u['id']}/credits", headers=admin, json={"amount": 0})
        assert r.status_code == 400
        hist = requests.get(f"{API}/admin/users/{u['id']}/credits", headers=admin).json()
        assert [t["amount"] for t in hist] == [-20, 50]
        c = requests.get(f"{API}/credits", headers=h).json()
        assert c["balance"] == 30 and "by" not in c["history"][0]

    def test_customer_cannot_adjust(self, cust):
        r = requests.post(f"{API}/admin/users/{cust[1]['id']}/credits", headers=cust[0], json={"amount": 100})
        assert r.status_code in (401, 403)

    def test_company_credits_toggle_and_inherit(self, admin, cities):
        comp = f"TEST_Credit Bygg {TAG} co"
        h1, u1 = register(cities, 0, company=comp)
        r = requests.post(f"{API}/admin/companies/credits", headers=admin, json={"name": f"  test_credit bygg {TAG.upper()}  CO ", "enabled": True})
        assert r.status_code == 200 and r.json()["credits_enabled"] is True and r.json()["updated"] >= 1
        assert requests.get(f"{API}/credits", headers=h1).json()["enabled"] is True
        cos = requests.get(f"{API}/admin/companies", headers=admin).json()
        co = next(c for c in cos if c["name"].lower() == comp.lower())
        assert co["credits_enabled"] is True
        h2, u2 = register(cities, 0, company=comp)
        assert u2["credits_enabled"] is True
        requests.post(f"{API}/admin/companies/credits", headers=admin, json={"name": comp, "enabled": False})
        assert requests.get(f"{API}/credits", headers=h2).json()["enabled"] is False


# ---------- Broadcast ----------
class TestBroadcast:
    def test_broadcast_city(self, admin, cities, cust):
        h3, u3 = register(cities, 2, company=f"TEST_Credit Bygg {TAG} bc")
        r = requests.post(f"{API}/admin/broadcast", headers=admin, json={"title": f"TEST_Info {TAG}", "body": "Stängt på fredag", "city_id": cities[2]["id"]})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["recipients"] >= 1 and rec["city_id"] == cities[2]["id"]
        n3 = requests.get(f"{API}/notifications", headers=h3).json()
        items = n3 if isinstance(n3, list) else n3.get("items", n3)
        assert any(n["kind"] == "broadcast" and n["title"] == f"TEST_Info {TAG}" for n in items)
        n1 = requests.get(f"{API}/notifications", headers=cust[0]).json()
        items1 = n1 if isinstance(n1, list) else n1.get("items", n1)
        assert not any(n["title"] == f"TEST_Info {TAG}" for n in items1)
        lst = requests.get(f"{API}/admin/broadcasts", headers=admin).json()
        assert lst[0]["id"] == rec["id"]

    def test_broadcast_all_and_validation(self, admin, cust):
        r = requests.post(f"{API}/admin/broadcast", headers=admin, json={"title": "  ", "body": "x"})
        assert r.status_code in (400, 422)
        r = requests.post(f"{API}/admin/broadcast", headers=admin, json={"title": "x", "body": "y", "city_id": "bogus"})
        assert r.status_code == 400
        r = requests.post(f"{API}/admin/broadcast", headers=cust[0], json={"title": "x", "body": "y"})
        assert r.status_code in (401, 403)
        r = requests.post(f"{API}/admin/broadcast", headers=admin, json={"title": f"TEST_All {TAG}", "body": "Hej alla"})
        assert r.status_code == 200
        active = mdb.users.count_documents({"disabled": {"$ne": True}, "role": {"$ne": "admin"}})
        assert r.json()["recipients"] == active
        n1 = requests.get(f"{API}/notifications", headers=cust[0]).json()
        items1 = n1 if isinstance(n1, list) else n1.get("items", n1)
        assert any(n["title"] == f"TEST_All {TAG}" for n in items1)


# ---------- Visibility ----------
class TestVisibility:
    def test_hide_product_for_city(self, admin, cities, cust, product):
        pn = product["part_no"]
        r = requests.put(f"{API}/admin/products/{pn}/visibility", headers=admin, json={"hidden_city_ids": [cities[0]["id"]]})
        assert r.status_code == 200 and r.json()["hidden_city_ids"] == [cities[0]["id"]]
        try:
            assert requests.get(f"{API}/products/{pn}", headers=cust[0]).status_code == 404
            res = requests.get(f"{API}/products", headers=cust[0], params={"q": pn}).json()
            assert all(p["part_no"] != pn for p in res["items"])
            r = requests.post(f"{API}/orders", headers=cust[0], json={"items": [{"part_no": pn, "size": product["sizes"][0], "quantity": 1}],
                                                                      "delivery": {"method": "store"}})
            assert r.status_code == 400
            ad = requests.get(f"{API}/products/{pn}", headers=admin).json()
            assert ad["hidden_city_ids"] == [cities[0]["id"]]
            h_other, _ = register(cities, 1, company=f"TEST_Credit Bygg {TAG} vis")
            assert requests.get(f"{API}/products/{pn}", headers=h_other).status_code == 200
            assert requests.put(f"{API}/admin/products/{pn}/visibility", headers=admin, json={"hidden_city_ids": ["bogus"]}).status_code == 400
            assert requests.put(f"{API}/admin/products/NOPE/visibility", headers=admin, json={"hidden_city_ids": []}).status_code == 404
        finally:
            requests.put(f"{API}/admin/products/{pn}/visibility", headers=admin, json={"hidden_city_ids": []})


# ---------- Purchase ranking ----------
class TestPurchaseRanking:
    def test_ranking_and_color_filter(self, cities):
        h, u = register(cities, 3, company=f"TEST_Credit Bygg {TAG} rank")
        black = mdb.products.find_one({"colors": {"$elemMatch": {"base": ["Svart"]}}, "sort_index": {"$gt": 200}}, {"_id": 0})
        other = mdb.products.find_one({"colors.0": {"$exists": True}, "colors.base": {"$ne": "Svart"}, "sort_index": {"$gt": 300}}, {"_id": 0})
        bcol = next(c for c in black["colors"] if c.get("base") == ["Svart"])
        now = datetime.now(timezone.utc)
        mdb.orders.insert_many([
            {"id": str(uuid.uuid4()), "user_id": u["id"], "status": "confirmed", "created_at": (now - timedelta(days=2)).isoformat(),
             "items": [{"part_no": black["part_no"], "color_code": bcol["code"], "size": "M", "quantity": 1}], "order_number": "TESTR1"},
            {"id": str(uuid.uuid4()), "user_id": u["id"], "status": "new", "created_at": now.isoformat(),
             "items": [{"part_no": other["part_no"], "color_code": other["colors"][0]["code"], "size": "M", "quantity": 1}], "order_number": "TESTR2"},
        ])
        items = requests.get(f"{API}/products", headers=h).json()["items"]
        assert [p["part_no"] for p in items[:2]] == [other["part_no"], black["part_no"]]
        assert items[0]["purchased"] is True and items[0]["purchased_color"] == other["colors"][0]["code"]
        assert items[1]["purchased_color"] == bcol["code"]
        assert not items[2].get("purchased")
        items = requests.get(f"{API}/products", headers=h, params={"filters": json.dumps({"Color": ["Svart"]})}).json()["items"]
        assert items[0]["part_no"] == black["part_no"] and items[0]["purchased"] is True
        assert all(p["part_no"] != other["part_no"] or not p.get("purchased") for p in items)
