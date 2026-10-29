# Iteration 7: real (max 2 emails) order-reply integration: email-link confirm + admin in-app reply
import os
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ORDER_ID = os.environ.get("ITER7_ORDER_ID", "bc22a5ef-b42a-4ec7-9a89-31924b742504")  # existing B10031 of delivered@resend.dev


@pytest.fixture(scope="module")
def order():
    o = mdb.orders.find_one({"id": ORDER_ID}, {"_id": 0})
    if not o:
        pytest.skip("order not found")
    return o


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@blaklader.local", "password": "Admin123!"})
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code}")
    d = r.json()
    return d.get("token") or d.get("access_token")


def test_reply_page_get(order):
    r = requests.get(f"{BASE_URL}/api/order-reply/{order['confirm_token']}")
    assert r.status_code == 200 and "Bekräfta order" in r.text and order["order_number"] in r.text


def test_email_link_confirm(order):
    before = len(order.get("replies", []))
    r = requests.post(f"{BASE_URL}/api/order-reply/{order['confirm_token']}",
                      data={"message": "TEST_ Leverans sker torsdag v.24"}, timeout=60)
    assert r.status_code == 200
    print(r.text[-600:])
    assert "Svar skickat" in r.text, r.text[-800:]
    o = mdb.orders.find_one({"id": ORDER_ID}, {"_id": 0})
    assert o["status"] == "confirmed" and len(o["replies"]) == before + 1
    assert o["replies"][-1]["message"] == "TEST_ Leverans sker torsdag v.24"


def test_admin_in_app_reply(order, admin_token):
    before = len(mdb.orders.find_one({"id": ORDER_ID})["replies"])
    r = requests.post(f"{BASE_URL}/api/admin/orders/{ORDER_ID}/reply", json={"message": "TEST_ Admin svar: levereras fredag"},
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    print(r.status_code, r.text[:300])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "confirmed" and "confirm_token" not in d and "_id" not in d
    assert len(d["replies"]) == before + 1 and d["replies"][-1]["message"] == "TEST_ Admin svar: levereras fredag"


def test_admin_reply_empty_rejected(admin_token):
    r = requests.post(f"{BASE_URL}/api/admin/orders/{ORDER_ID}/reply", json={"message": "   "},
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code in (400, 422)
