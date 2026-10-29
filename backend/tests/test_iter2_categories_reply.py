# Iteration 2: category tree, group/category filtering, order confirm_token hiding, order-reply HTML flow
import os
import re

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@blaklader.local", "password": "Admin123!"}
CUSTOMER = {"email": "delivered@resend.dev", "password": "secret12"}
EXPECTED_GROUPS = {"Överdelar", "Underdelar", "Underställ", "Underkläder", "Vattentäta plagg", "Handskar", "Arbetsskor", "Tillbehör"}


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
        pytest.skip(f"login failed {creds['email']}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def cust_h():
    return _login(CUSTOMER)


@pytest.fixture(scope="module")
def admin_h():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def tree(cust_h):
    r = requests.get(f"{BASE_URL}/api/categories", headers=cust_h)
    assert r.status_code == 200
    return r.json()


# ---- categories tree
class TestCategories:
    def test_groups_present(self, tree):
        names = {g["name"] for g in tree}
        assert EXPECTED_GROUPS <= names, names

    def test_group_shape(self, tree):
        for g in tree:
            assert isinstance(g["slug"], str) and g["slug"]
            assert isinstance(g["count"], int) and g["count"] > 0
            assert isinstance(g["children"], list)
            for c in g["children"]:
                assert set(["slug", "name", "count"]) <= set(c) and c["count"] > 0

    def test_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/categories").status_code in (401, 403)


# ---- products filtering
class TestProductFilter:
    def test_total_active(self, cust_h):
        d = requests.get(f"{BASE_URL}/api/products", headers=cust_h).json()
        print("total products", d["total"])
        assert 1100 <= d["total"] <= 1400

    def test_group_count_matches_tree(self, cust_h, tree):
        g = next(g for g in tree if g["slug"] == "underdelar")
        d = requests.get(f"{BASE_URL}/api/products?group=underdelar&page_size=60", headers=cust_h).json()
        assert d["total"] == g["count"]
        assert all("underdelar" in p.get("groups", []) for p in d["items"])

    def test_group_and_category(self, cust_h, tree):
        g = next(g for g in tree if g["slug"] == "underdelar")
        byxor = next(c for c in g["children"] if c["slug"] == "byxor")
        d = requests.get(f"{BASE_URL}/api/products?group=underdelar&category=byxor&page_size=60", headers=cust_h).json()
        assert d["total"] == byxor["count"] and d["total"] > 0
        assert all("byxor" in p.get("categories", []) for p in d["items"])

    def test_q_combined(self, cust_h):
        all_ = requests.get(f"{BASE_URL}/api/products?group=underdelar&category=byxor", headers=cust_h).json()["total"]
        d = requests.get(f"{BASE_URL}/api/products?group=underdelar&category=byxor&q=hantverk&page_size=60", headers=cust_h).json()
        print("byxor+hantverk", d["total"], "of", all_)
        assert d["total"] <= all_
        assert all("hantverk" in p["name"].lower() or "hantverk" in p["part_no"].lower() for p in d["items"])

    def test_unknown_group_empty(self, cust_h):
        d = requests.get(f"{BASE_URL}/api/products?group=nope_xyz", headers=cust_h).json()
        assert d["total"] == 0 and d["items"] == []


# ---- order create + reply
@pytest.fixture(scope="module")
def order(cust_h, db):
    p = requests.get(f"{BASE_URL}/api/products?group=underdelar&category=byxor", headers=cust_h).json()["items"][0]
    item = {"part_no": p["part_no"], "size": (p.get("sizes") or ["C50"])[0], "quantity": 2,
            "color_code": (p.get("colors") or [{}])[0].get("code")}
    r = requests.post(f"{BASE_URL}/api/orders", headers=cust_h, json={"items": [item], "comment": "TEST_iter2 order"})
    assert r.status_code == 200, r.text
    o = r.json()
    tok = db.orders.find_one({"id": o["id"]})["confirm_token"]
    return {"order": o, "token": tok}


class TestOrderReply:
    def test_create_status_and_no_token(self, order):
        o = order["order"]
        assert o["status"] == "new" and o["replies"] == [] and "confirm_token" not in o
        assert o["email_status"] == "sent"

    def test_lists_hide_token(self, order, cust_h, admin_h):
        mine = requests.get(f"{BASE_URL}/api/orders", headers=cust_h).json()
        allo = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_h).json()
        assert all("confirm_token" not in o for o in mine + allo)
        assert any(o["id"] == order["order"]["id"] for o in mine)

    def test_reply_page_get(self, order):
        r = requests.get(f"{BASE_URL}/api/order-reply/{order['token']}")
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
        assert order["order"]["order_number"] in r.text and "<textarea" in r.text and 'name="message"' in r.text

    def test_reply_page_invalid(self):
        r = requests.get(f"{BASE_URL}/api/order-reply/invalidtoken_xxxxxxxxxxxxxxxxx")
        assert r.status_code == 200 and "Ordern hittades inte" in r.text
        r2 = requests.get(f"{BASE_URL}/api/order-reply/short")
        assert "Ordern hittades inte" in r2.text

    def test_empty_message_error(self, order, db):
        r = requests.post(f"{BASE_URL}/api/order-reply/{order['token']}", data={"message": "   "})
        assert "Skriv ett meddelande" in r.text
        assert db.orders.find_one({"id": order["order"]["id"]})["status"] == "new"

    def test_cvv_message_blocked(self, order, db):
        r = requests.post(f"{BASE_URL}/api/order-reply/{order['token']}", data={"message": "skicka ditt cvv"})
        assert "otillåtna ord" in r.text
        doc = db.orders.find_one({"id": order["order"]["id"]})
        assert doc["status"] == "new" and doc["replies"] == []

    def test_reply_success(self, order, db, cust_h):
        msg = "TEST leverans sker om 15 min"
        r = requests.post(f"{BASE_URL}/api/order-reply/{order['token']}", data={"message": msg})
        assert r.status_code == 200 and "Svar skickat" in r.text, re.sub(r"<[^>]+>", " ", r.text)[-400:]
        doc = db.orders.find_one({"id": order["order"]["id"]})
        assert doc["status"] == "confirmed" and doc["replies"][-1]["message"] == msg
        mine = requests.get(f"{BASE_URL}/api/orders", headers=cust_h).json()
        o = next(o for o in mine if o["id"] == order["order"]["id"])
        assert o["status"] == "confirmed" and o["replies"][-1]["message"] == msg

    def test_reply_page_shows_previous(self, order):
        r = requests.get(f"{BASE_URL}/api/order-reply/{order['token']}")
        assert "Tidigare svar" in r.text and "leverans sker om 15 min" in r.text

    def test_xss_escaped(self, order):
        r = requests.post(f"{BASE_URL}/api/order-reply/{order['token']}", data={"message": "<script>alert(1)</script> ok"})
        assert "<script>alert(1)</script>" not in r.text
