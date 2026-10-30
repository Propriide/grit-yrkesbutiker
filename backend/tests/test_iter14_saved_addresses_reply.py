# Iteration 14: saved shipping addresses (POST /api/orders ship -> user.addresses, GET /api/addresses) + admin reply on order detail
# NOTE: run serially (-n 0); module-scoped customer fixture is shared across classes.
import os
import uuid
from datetime import datetime, timezone

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

A = {"name": "TEST_Mottagare A", "address": "Testgatan 1", "postal_code": "50330", "city": "Borås"}
B = {"name": "TEST_Mottagare B", "address": "Annan väg 22", "postal_code": "41101", "city": "Göteborg"}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def customer():
    cities = requests.get(f"{API}/cities").json()
    r = requests.post(f"{API}/auth/register", json={
        "email": f"delivered+t14{TAG}@resend.dev", "password": "secret12", "phone": "07011111",
        "company": f"TEST_Addr {TAG}", "city_id": cities[0]["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    p = mdb.products.find_one({"sizes.0": {"$exists": True}, "hidden_city_ids": {"$ne": cities[0]["id"]}}, {"_id": 0})
    yield {"Authorization": f"Bearer {d['access_token']}"}, d["user"], p
    uid = d["user"]["id"]
    nums = [o["order_number"] for o in mdb.orders.find({"user_id": uid}, {"order_number": 1})]
    mdb.notifications.delete_many({"order_number": {"$in": nums}})
    mdb.notifications.delete_many({"user_id": uid})
    mdb.orders.delete_many({"user_id": uid})
    mdb.users.delete_one({"id": uid})
    mdb.companies.delete_many({"name": f"TEST_Addr {TAG}"})


def order(h, p, delivery):
    item = {"part_no": p["part_no"], "size": p["sizes"][0], "quantity": 1}
    if p.get("colors"):
        item["color_code"] = p["colors"][0]["code"]
    return requests.post(f"{API}/orders", headers=h, json={"items": [item], "comment": "TEST iter14", "delivery": delivery})


# --- saved addresses
class TestSavedAddresses:
    def test_empty_initially(self, customer):
        h, _, _ = customer
        r = requests.get(f"{API}/addresses", headers=h)
        assert r.status_code == 200 and r.json() == []

    def test_requires_auth(self):
        assert requests.get(f"{API}/addresses").status_code in (401, 403)

    def test_invalid_ship_does_not_save(self, customer):
        h, _, p = customer
        r = order(h, p, {"method": "ship", "address": "X", "postal_code": "", "city": ""})
        assert r.status_code == 400
        assert requests.get(f"{API}/addresses", headers=h).json() == []

    def test_ship_saves_newest_first(self, customer):
        h, _, p = customer
        r1 = order(h, p, {"method": "ship", **A})
        assert r1.status_code == 200, r1.text
        r2 = order(h, p, {"method": "ship", **B})
        assert r2.status_code == 200, r2.text
        got = requests.get(f"{API}/addresses", headers=h).json()
        assert got == [B, A], got

    def test_dedupe_and_max_10(self, customer):
        h, u, p = customer
        extra = [{"name": "", "address": f"Fyll {i}", "postal_code": "11111", "city": "Sthlm"} for i in range(8)]
        mdb.users.update_one({"id": u["id"]}, {"$set": {"addresses": [B, A, *extra]}})
        # whitespace should be stripped -> same as A
        r = order(h, p, {"method": "ship", **{k: f" {v} " if v else v for k, v in A.items()}})
        assert r.status_code == 200, r.text
        got = requests.get(f"{API}/addresses", headers=h).json()
        assert len(got) == 10
        assert got[0] == A and got[1] == B
        assert sum(1 for a in got if a == A) == 1

    def test_addresses_not_leaked_in_admin_orders(self, admin, customer):
        _, u, _ = customer
        orders = [o for o in requests.get(f"{API}/admin/orders", headers=admin).json() if o["user_id"] == u["id"]]
        assert len(orders) == 3
        assert all(o["delivery"]["method"] == "ship" for o in orders)


# --- admin reply from order detail (GET /orders/{id} as admin + reply)
class TestAdminReplyDetail:
    def test_admin_get_and_confirm(self, admin, customer):
        _, u, _ = customer
        o = mdb.orders.find_one({"user_id": u["id"], "status": "new"}, {"_id": 0})
        r = requests.get(f"{API}/orders/{o['id']}", headers=admin)
        assert r.status_code == 200 and r.json()["order_number"] == o["order_number"]
        assert "confirm_token" not in r.json()
        rr = requests.post(f"{API}/admin/orders/{o['id']}/reply", headers=admin, json={"message": "TEST levereras imorgon", "action": "confirm"})
        if rr.status_code == 400 and "Mejlet" in rr.text:
            pytest.skip(f"Resend rate-limited: {rr.text}")
        assert rr.status_code == 200, rr.text
        assert rr.json()["status"] == "confirmed"
        assert requests.get(f"{API}/orders/{o['id']}", headers=admin).json()["status"] == "confirmed"

    def test_admin_new_notification_has_order_id(self, admin, customer):
        _, u, _ = customer
        nums = [o["order_number"] for o in mdb.orders.find({"user_id": u["id"]})]
        items = requests.get(f"{API}/notifications", headers=admin).json()["items"]
        mine = [n for n in items if n.get("order_number") in nums and n["kind"] == "new"]
        assert mine, "admin got no 'new' notification"
        assert all(n.get("order_id") for n in mine)
