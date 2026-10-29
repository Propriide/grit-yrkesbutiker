# Iteration 8: notifications, order timeline (confirm/decline), email-link decline, colour ranking
# NOTE: sends at most 3 real emails (1 new order -> prii_de@hotmail.com, 1 email-link decline, 1 admin confirm)
import os
import json
import re
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STATE = {}


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def cust():
    return login("delivered@resend.dev", "secret12")


@pytest.fixture(scope="module")
def other():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "secret12", "phone": "0701234567", "company": "TEST_Other AB",
                      "city_id": (mdb.cities.find_one({}, {"_id": 0, "id": 1}) or {}).get("id")})
    assert r.status_code == 200, r.text
    yield {"Authorization": f"Bearer {r.json()['access_token']}"}
    mdb.users.delete_many({"email": email})


# --- notifications basics
class TestNotifications:
    def test_get_shape(self, cust):
        r = requests.get(f"{BASE_URL}/api/notifications", headers=cust)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["items"], list) and isinstance(d["unread"], int)
        assert d["unread"] == sum(1 for n in d["items"] if not n["read"])

    def test_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/notifications").status_code in (401, 403)


# --- order create -> admin notification; reply confirm -> customer notification
class TestOrderFlow:
    def test_create_order_notifies_admins(self, cust, admin):
        before = requests.get(f"{BASE_URL}/api/notifications", headers=admin).json()["unread"]
        p = requests.get(f"{BASE_URL}/api/products?page_size=5", headers=cust).json()["items"][0]
        p = requests.get(f"{BASE_URL}/api/products/{p['part_no']}", headers=cust).json()
        item = {"part_no": p["part_no"], "size": p["sizes"][0], "quantity": 1}
        if p.get("colors"):
            item["color_code"] = p["colors"][0]["code"]
        r = requests.post(f"{BASE_URL}/api/orders", headers=cust, json={"items": [item], "comment": "TEST_iter8"})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "new" and o["email_status"] == "sent", o
        assert "confirm_token" not in o and "sent_to" not in o
        STATE["order"] = o
        n = requests.get(f"{BASE_URL}/api/notifications", headers=admin).json()
        assert n["unread"] == before + 1
        top = n["items"][0]
        assert top["kind"] == "new" and top["order_id"] == o["id"] and top["read"] is False
        STATE["admin_notif"] = top["id"]
        # both admins notified
        assert mdb.notifications.count_documents({"order_id": o["id"], "kind": "new"}) == 2

    def test_get_order_owner_admin_other(self, cust, admin, other):
        o = STATE.get("order") or mdb.orders.find_one({"comment": "TEST_iter8"}, {"_id": 0}, sort=[("created_at", -1)])
        oid = o["id"]
        r = requests.get(f"{BASE_URL}/api/orders/{oid}", headers=cust)
        assert r.status_code == 200 and r.json()["order_number"] == o["order_number"]
        assert "confirm_token" not in r.json()
        assert requests.get(f"{BASE_URL}/api/orders/{oid}", headers=admin).status_code == 200
        assert requests.get(f"{BASE_URL}/api/orders/{oid}", headers=other).status_code == 404

    def test_mark_read_only_own(self, admin, cust):
        nid = STATE["admin_notif"]
        requests.post(f"{BASE_URL}/api/notifications/{nid}/read", headers=cust)  # foreign -> must not mark
        assert mdb.notifications.find_one({"id": nid})["read"] is False
        r = requests.post(f"{BASE_URL}/api/notifications/{nid}/read", headers=admin)
        assert r.status_code == 200
        assert mdb.notifications.find_one({"id": nid})["read"] is True

    def test_invalid_action_400(self, admin):
        r = requests.post(f"{BASE_URL}/api/admin/orders/{STATE['order']['id']}/reply", headers=admin, json={"message": "x", "action": "bogus"})
        assert r.status_code == 400

    def test_reply_requires_admin(self, cust):
        r = requests.post(f"{BASE_URL}/api/admin/orders/{STATE['order']['id']}/reply", headers=cust, json={"message": "x", "action": "confirm"})
        assert r.status_code in (401, 403)

    def test_admin_confirm(self, admin, cust):
        before = requests.get(f"{BASE_URL}/api/notifications", headers=cust).json()["unread"]
        r = requests.post(f"{BASE_URL}/api/admin/orders/{STATE['order']['id']}/reply", headers=admin,
                          json={"message": "TEST_iter8 Leverans torsdag", "action": "confirm"})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "confirmed" and o["replies"][-1]["action"] == "confirm" and o.get("confirmed_at")
        n = requests.get(f"{BASE_URL}/api/notifications", headers=cust).json()
        assert n["unread"] == before + 1
        assert n["items"][0]["kind"] == "confirmed" and n["items"][0]["order_id"] == o["id"]

    def test_read_all(self, cust):
        assert requests.post(f"{BASE_URL}/api/notifications/read-all", headers=cust).status_code == 200
        assert requests.get(f"{BASE_URL}/api/notifications", headers=cust).json()["unread"] == 0


# --- email-link page decline
class TestEmailLinkDecline:
    def test_page_has_both_buttons(self):
        o = mdb.orders.find_one({"order_number": "B10024"}, {"_id": 0})
        STATE["b24"] = o
        r = requests.get(f"{BASE_URL}/api/order-reply/{o['confirm_token']}")
        assert r.status_code == 200
        assert 'value="confirm"' in r.text and 'value="decline"' in r.text

    def test_post_decline(self, cust):
        o = STATE["b24"]
        r = requests.post(f"{BASE_URL}/api/order-reply/{o['confirm_token']}", data={"message": "TEST_iter8 Slut i lager", "action": "decline"})
        assert r.status_code == 200
        assert "markerad som nekad" in r.text, r.text[-600:]
        o2 = requests.get(f"{BASE_URL}/api/orders/{o['id']}", headers=cust).json()
        assert o2["status"] == "declined" and o2["replies"][-1]["action"] == "decline"
        n = requests.get(f"{BASE_URL}/api/notifications", headers=cust).json()
        assert n["items"][0]["kind"] == "declined" and n["items"][0]["order_id"] == o["id"]


# --- colour ranking
class TestColourRanking:
    def test_svart_solid_first(self, cust):
        f = json.dumps({"Color": ["Svart"]})
        d = requests.get(f"{BASE_URL}/api/products", headers=cust, params={"filters": f, "page_size": 24}).json()
        assert d["total"] == 844, d["total"]
        bad = [p["part_no"] for p in d["items"] if not any(c["name"] == "Svart" for c in p.get("colors", []))]
        assert not bad, f"non-solid in first page: {bad}"

    def test_bla_solid_first(self, cust):
        f = json.dumps({"Color": ["Blå"]})
        d = requests.get(f"{BASE_URL}/api/products", headers=cust, params={"filters": f, "page_size": 24}).json()
        bad = [(p["part_no"], [c["name"] for c in p.get("colors", [])]) for p in d["items"]
               if not any("/" not in c["name"] and "Blå" in (c.get("base") or []) for c in p.get("colors", []))]
        assert not bad, bad
