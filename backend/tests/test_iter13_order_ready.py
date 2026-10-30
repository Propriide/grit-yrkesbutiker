# Iteration 13: admin "klarmarkera" (POST /api/admin/orders/{id}/ready) + customer in-app 'ready' notification
# Orders are inserted directly in DB (no email sent) to avoid Resend rate limits.
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
        "email": f"delivered+t13{TAG}@resend.dev", "password": "secret12", "phone": "07011111",
        "company": f"TEST_Ready {TAG}", "city_id": cities[0]["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    yield {"Authorization": f"Bearer {d['access_token']}"}, d["user"]
    uid = d["user"]["id"]
    mdb.orders.delete_many({"user_id": uid})
    mdb.notifications.delete_many({"user_id": uid})
    mdb.notifications.delete_many({"order_number": {"$regex": f"^TEST13{TAG}"}})
    mdb.users.delete_many({"id": uid})
    mdb.companies.delete_many({"name": {"$regex": f"^TEST_Ready {TAG}"}})


def seed_order(user, status):
    oid = str(uuid.uuid4())
    mdb.orders.insert_one({
        "id": oid, "order_number": f"TEST13{TAG}{oid[:4]}", "user_id": user["id"],
        "customer": {"email": user["email"], "company": user.get("company", ""), "phone": "", "org_number": "", "city_name": ""},
        "items": [{"part_no": "X1", "name": "TEST item", "size": "M", "quantity": 2, "color_code": None, "color_name": None, "image_url": None}],
        "comment": "", "delivery": {"method": "store"}, "order_value": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        "email_status": "sent", "sent_to": "x@resend.dev", "status": status, "confirm_token": uuid.uuid4().hex + uuid.uuid4().hex,
        "replies": [{"message": "OK", "created_at": datetime.now(timezone.utc).isoformat(), "action": "confirm"}] if status == "confirmed" else []})
    return oid


class TestMarkReady:
    def test_requires_auth(self):
        r = requests.post(f"{API}/admin/orders/whatever/ready")
        assert r.status_code in (401, 403)

    def test_customer_forbidden(self, customer):
        h, u = customer
        oid = seed_order(u, "confirmed")
        r = requests.post(f"{API}/admin/orders/{oid}/ready", headers=h)
        assert r.status_code == 403
        assert mdb.orders.find_one({"id": oid})["status"] == "confirmed"

    def test_unknown_404(self, admin):
        r = requests.post(f"{API}/admin/orders/{uuid.uuid4()}/ready", headers=admin)
        assert r.status_code == 404
        assert r.json()["detail"] == "Ordern hittades inte"

    @pytest.mark.parametrize("status", ["new", "declined"])
    def test_not_confirmed_400(self, admin, customer, status):
        oid = seed_order(customer[1], status)
        r = requests.post(f"{API}/admin/orders/{oid}/ready", headers=admin)
        assert r.status_code == 400
        assert "bekräftade" in r.json()["detail"]
        assert mdb.orders.find_one({"id": oid})["status"] == status

    def test_ready_flow_and_notification(self, admin, customer):
        h, u = customer
        oid = seed_order(u, "confirmed")
        r = requests.post(f"{API}/admin/orders/{oid}/ready", headers=admin)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "ready" and d.get("ready_at")
        assert "_id" not in d and "confirm_token" not in d
        # customer sees ready order
        o = requests.get(f"{API}/orders/{oid}", headers=h).json()
        assert o["status"] == "ready" and o["ready_at"] == d["ready_at"]
        assert "order_value" not in o and "confirm_token" not in o
        # notification for owner
        n = requests.get(f"{API}/notifications", headers=h).json()
        ready = [x for x in n["items"] if x["kind"] == "ready" and x["order_id"] == oid]
        assert len(ready) == 1
        assert ready[0]["title"] == f"Order {o['order_number']} är klar"
        assert ready[0]["read"] is False and n["unread"] >= 1
        # second call -> 400 (already ready), no duplicate notification
        r2 = requests.post(f"{API}/admin/orders/{oid}/ready", headers=admin)
        assert r2.status_code == 400
        n2 = requests.get(f"{API}/notifications", headers=h).json()
        assert len([x for x in n2["items"] if x["kind"] == "ready" and x["order_id"] == oid]) == 1

    def test_admin_list_shows_ready(self, admin, customer):
        lst = requests.get(f"{API}/admin/orders", headers=admin).json()
        mine = [o for o in lst if o["user_id"] == customer[1]["id"]]
        assert any(o["status"] == "ready" for o in mine)
        assert all("confirm_token" not in o for o in mine)
