# Iteration 18: regression after backend refactor (order_emails.py + routes/notifications.py split). Run serially.
import os
import time
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
SHIP = {"method": "ship", "name": "TEST_Mottagare", "address": "Testgatan 18", "postal_code": "50330", "city": "Borås"}


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
    """Fresh TEST_ customer (recipient via delivered+...@resend.dev sink); removed after module."""
    cities = requests.get(f"{API}/cities").json()
    email = f"delivered+t18{TAG}@resend.dev"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "secret12", "phone": "0701818181", "name": "TEST Iter18",
        "company": f"TEST_Iter18 {TAG}", "city_id": cities[0]["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    yield {"h": {"Authorization": f"Bearer {d['access_token']}"}, "user": d["user"], "email": email}
    uid = d["user"]["id"]
    mdb.orders.delete_many({"user_id": uid})
    mdb.notifications.delete_many({"user_id": uid})
    mdb.favorites.delete_many({"user_id": uid})
    mdb.users.delete_one({"id": uid})


@pytest.fixture(scope="module")
def product(customer):
    items = requests.get(f"{API}/products", headers=customer["h"], params={"limit": 5}).json()
    items = items.get("items", items) if isinstance(items, dict) else items
    p = next(x for x in items if x.get("sizes"))
    full = requests.get(f"{API}/products/{p['part_no']}", headers=customer["h"]).json()
    return full


def item(p, qty=1):
    return {"part_no": p["part_no"], "size": p["sizes"][0], "quantity": qty,
            "color_code": (p.get("colors") or [{}])[0].get("code")}


# --- Auth
class TestAuth:
    def test_admin_login_me(self, admin):
        me = requests.get(f"{API}/auth/me", headers=admin).json()
        assert me["role"] == "admin" and me["email"] == "admin@blaklader.local" and "password_hash" not in me

    def test_customer_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": "delivered@resend.dev", "password": "secret12"})
        assert r.status_code == 200 and r.json()["user"]["role"] == "customer"

    def test_wrong_password_401(self, customer):
        r = requests.post(f"{API}/auth/login", json={"email": customer["email"], "password": "wrong!!"})
        assert r.status_code == 401

    def test_me_unauth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401


# --- Catalog, favorites, credits
class TestCatalog:
    def test_categories_products(self, customer, product):
        assert requests.get(f"{API}/categories", headers=customer["h"]).status_code == 200
        assert product["part_no"] and product["sizes"]

    def test_unknown_product_404(self, customer):
        assert requests.get(f"{API}/products/NOPE_{TAG}", headers=customer["h"]).status_code == 404

    def test_favorites_and_credits(self, customer, product):
        r = requests.post(f"{API}/favorites", headers=customer["h"], json={"part_no": product["part_no"],
                          "color_code": (product.get("colors") or [{}])[0].get("code")})
        assert r.status_code == 200, r.text
        favs = requests.get(f"{API}/favorites", headers=customer["h"]).json()
        assert any(f["part_no"] == product["part_no"] for f in favs)
        c = requests.get(f"{API}/credits", headers=customer["h"])
        assert c.status_code == 200 and "_id" not in c.text


# --- Orders + email + reply page (moved templates)
class TestOrders:
    def test_invalid_delivery(self, customer, product):
        r = requests.post(f"{API}/orders", headers=customer["h"], json={"items": [item(product)], "delivery": {"method": "x"}})
        assert r.status_code == 400
        r = requests.post(f"{API}/orders", headers=customer["h"], json={"items": [item(product)], "delivery": {"method": "ship", "name": "A"}})
        assert r.status_code == 400 and "adress" in r.json()["detail"]

    def test_store_and_parcel(self, customer, product):
        for m in ("store", "parcel_box"):
            r = requests.post(f"{API}/orders", headers=customer["h"], json={"items": [item(product)], "delivery": {"method": m}})
            assert r.status_code == 200, r.text
            o = r.json()
            assert o["delivery"] == {"method": m} and o["email_status"] == "sent"
            assert "confirm_token" not in o and "sent_to" not in o and "order_value" not in o
            time.sleep(1)

    def test_ship_order_email_and_reply_flow(self, customer, product, admin):
        r = requests.post(f"{API}/orders", headers=customer["h"],
                          json={"items": [item(product, 2)], "delivery": SHIP, "comment": "TEST leverans v.24"})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["email_status"] == "sent" and o["status"] == "new" and o["order_number"].startswith("B")
        db_o = mdb.orders.find_one({"id": o["id"]})
        assert db_o["sent_to"] == "delivered@resend.dev" and db_o["email_status"] == "sent"
        # saved addresses
        addrs = requests.get(f"{API}/addresses", headers=customer["h"]).json()
        assert addrs[0] == {k: SHIP[k] for k in ("name", "address", "postal_code", "city")}
        # customer GET
        lst = requests.get(f"{API}/orders", headers=customer["h"]).json()
        assert lst[0]["id"] == o["id"] and "confirm_token" not in lst[0]
        assert requests.get(f"{API}/orders/{o['id']}", headers=customer["h"]).json()["delivery"]["city"] == "Borås"
        # reply page renders order block + delivery text
        tok = db_o["confirm_token"]
        page = requests.get(f"{API}/order-reply/{tok}")
        assert page.status_code == 200 and "text/html" in page.headers["content-type"]
        for s in (o["order_number"], "Skickas: TEST_Mottagare, Testgatan 18, 50330 Borås", "2 st", "TEST leverans v.24",
                  f'action="/api/order-reply/{tok}"', "Bekräfta & skicka"):
            assert s in page.text, s
        assert "Länken är ogiltig" in requests.get(f"{API}/order-reply/invalidtoken_{TAG}xxxxxxxxxx").text
        # decline without message -> error
        r = requests.post(f"{API}/order-reply/{tok}", data={"message": "", "action": "decline"})
        assert "Skriv varför ordern nekas." in r.text
        # confirm via form
        r = requests.post(f"{API}/order-reply/{tok}", data={"message": "Leverans torsdag", "action": "confirm"})
        assert r.status_code == 200 and "Svar skickat" in r.text and "bekräftad" in r.text
        o2 = requests.get(f"{API}/orders/{o['id']}", headers=customer["h"]).json()
        assert o2["status"] == "confirmed" and o2["replies"][-1]["message"] == "Leverans torsdag"
        # admin mark ready
        time.sleep(1)
        r = requests.post(f"{API}/admin/orders/{o['id']}/ready", headers=admin)
        assert r.status_code == 200 and r.json()["status"] == "ready" and "confirm_token" not in r.json()
        # admin reply on ready keeps ready
        r = requests.post(f"{API}/admin/orders/{o['id']}/reply", headers=admin, json={"message": "Extra info", "action": "confirm"})
        assert r.status_code == 200 and r.json()["status"] == "ready"
        # customer notifications from confirm + ready
        n = requests.get(f"{API}/notifications", headers=customer["h"]).json()
        kinds = {x["kind"] for x in n["items"] if x.get("order_id") == o["id"]}
        assert {"confirmed", "ready"} <= kinds and n["unread"] >= 2

    def test_admin_decline(self, customer, product, admin):
        o = requests.post(f"{API}/orders", headers=customer["h"], json={"items": [item(product)], "delivery": {"method": "store"}}).json()
        r = requests.post(f"{API}/admin/orders/{o['id']}/reply", headers=admin, json={"message": "", "action": "decline"})
        assert r.status_code == 400
        assert requests.post(f"{API}/admin/orders/{o['id']}/ready", headers=admin).status_code == 400
        time.sleep(1)
        r = requests.post(f"{API}/admin/orders/{o['id']}/reply", headers=admin, json={"message": "Slut i lager", "action": "decline"})
        assert r.status_code == 200 and r.json()["status"] == "declined"
        adm = requests.get(f"{API}/admin/orders", headers=admin).json()
        assert any(x["id"] == o["id"] for x in adm) and all("confirm_token" not in x for x in adm[:20])

    def test_form_decline(self, customer, product):
        o = requests.post(f"{API}/orders", headers=customer["h"], json={"items": [item(product)], "delivery": {"method": "parcel_box"}}).json()
        tok = mdb.orders.find_one({"id": o["id"]})["confirm_token"]
        page = requests.get(f"{API}/order-reply/{tok}").text
        assert "Hämtas i paketbox" in page
        time.sleep(1)
        r = requests.post(f"{API}/order-reply/{tok}", data={"message": "TEST Slut i lager", "action": "decline"})
        assert "markerad som nekad" in r.text, r.text[-400:]
        o2 = requests.get(f"{API}/orders/{o['id']}", headers=customer["h"]).json()
        assert o2["status"] == "declined" and o2["replies"][-1]["action"] == "decline"
        assert "Tidigare svar" in requests.get(f"{API}/order-reply/{tok}").text

    def test_remove_address(self, customer):
        r = requests.post(f"{API}/addresses/remove", headers=customer["h"], json={k: SHIP[k] for k in ("name", "address", "postal_code", "city")})
        assert r.status_code == 200 and r.json() == []


# --- Notifications (moved router)
class TestNotifications:
    def test_unauth(self):
        assert requests.get(f"{API}/notifications").status_code == 401

    def test_read_one_and_all(self, customer):
        n = requests.get(f"{API}/notifications", headers=customer["h"]).json()
        assert n["items"], "expected notifications from order flow"
        nid = next(x["id"] for x in n["items"] if not x["read"])
        assert requests.post(f"{API}/notifications/{nid}/read", headers=customer["h"]).json() == {"ok": True}
        n2 = requests.get(f"{API}/notifications", headers=customer["h"]).json()
        assert n2["unread"] == n["unread"] - 1 and next(x for x in n2["items"] if x["id"] == nid)["read"] is True
        assert requests.post(f"{API}/notifications/read-all", headers=customer["h"]).json() == {"ok": True}
        assert requests.get(f"{API}/notifications", headers=customer["h"]).json()["unread"] == 0

    def test_admin_got_new_order_notification(self, admin, customer):
        n = requests.get(f"{API}/notifications", headers=admin).json()
        assert any(x["kind"] == "new" and customer["user"]["company"] in x["body"] for x in n["items"])


# --- Admin panel + push
class TestAdminPush:
    def test_admin_endpoints(self, admin, customer):
        for ep in ("/admin/users", "/admin/settings", "/admin/companies", "/admin/broadcasts", "/cities"):
            r = requests.get(f"{API}{ep}", headers=admin)
            assert r.status_code == 200 and '"_id"' not in r.text, ep
        assert requests.get(f"{API}/admin/settings", headers=admin).json().get("order_email") == "delivered@resend.dev"
        assert requests.get(f"{API}/admin/users", headers=customer["h"]).status_code == 403

    def test_webpush_and_native_push(self, customer):
        assert len(requests.get(f"{API}/webpush/public-key").json()["public_key"]) > 40
        assert requests.get(f"{API}/notification-prefs", headers=customer["h"]).status_code == 200
        r = requests.post(f"{API}/register-push", headers=customer["h"],
                          json={"device_token": f"ExponentPushToken[TEST{TAG}]", "platform": "ios"})
        if r.status_code == 500 and "EMERGENT_PUSH_KEY" in r.text:
            pytest.xfail("EMERGENT_PUSH_KEY is 'placeholder' in preview .env - native push relay rejects (env, not code)")
        assert r.status_code == 201 and r.json() == {"status": "registered"}, r.text


# --- Reply/ready flow on a DB-seeded order (no email to the real order recipient; replies go to the delivered+ sink)
class TestReplyFlowSeeded:
    def test_form_confirm_ready_admin_reply(self, customer, product, admin):
        u = customer["user"]
        oid, tok = f"TEST_{uuid.uuid4()}", f"TESTtok{uuid.uuid4().hex}"
        mdb.orders.insert_one({
            "id": oid, "order_number": f"TEST_B{TAG}", "user_id": u["id"],
            "customer": {"email": customer["email"], "company": u["company"], "phone": "0701818181", "org_number": "", "city_name": "Borås"},
            "items": [{"part_no": product["part_no"], "name": product["name"], "size": product["sizes"][0], "quantity": 2,
                       "color_code": None, "color_name": None, "image_url": None}],
            "comment": "TEST leverans v.24", "delivery": dict(SHIP), "order_value": 0, "created_at": "2026-01-01T00:00:00+00:00",
            "email_status": "sent", "sent_to": "x", "status": "new", "confirm_token": tok, "replies": []})
        page = requests.get(f"{API}/order-reply/{tok}").text
        for s in (f"TEST_B{TAG}", "Skickas: TEST_Mottagare, Testgatan 18, 50330 Borås", "2 st", "TEST leverans v.24", "Bekräfta & skicka"):
            assert s in page, s
        r = requests.post(f"{API}/order-reply/{tok}", data={"message": "Leverans torsdag", "action": "confirm"})
        assert "Svar skickat" in r.text and "markerad som bekräftad" in r.text, r.text[-300:]
        o2 = requests.get(f"{API}/orders/{oid}", headers=customer["h"]).json()
        assert o2["status"] == "confirmed" and o2["replies"][-1]["message"] == "Leverans torsdag" and "confirm_token" not in o2
        r = requests.post(f"{API}/admin/orders/{oid}/ready", headers=admin)
        assert r.status_code == 200 and r.json()["status"] == "ready"
        time.sleep(1)
        r = requests.post(f"{API}/admin/orders/{oid}/reply", headers=admin, json={"message": "", "action": "confirm"})
        assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["replies"][-1]["message"] == "Din order är bekräftad."
        n = requests.get(f"{API}/notifications", headers=customer["h"]).json()
        assert {"confirmed", "ready"} <= {x["kind"] for x in n["items"] if x.get("order_id") == oid}
        assert "Tidigare svar" in requests.get(f"{API}/order-reply/{tok}").text
