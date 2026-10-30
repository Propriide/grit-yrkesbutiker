# Iteration 17: PWA static assets, Web Push (VAPID) subscribe/unsubscribe, notification prefs,
# allowed_recipients pref filtering, admin broadcast targeting by companies (+ city)
import asyncio
import base64
import os
import sys
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
LOOP = asyncio.new_event_loop()  # motor client binds to the first loop; reuse one


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
    cs = requests.get(f"{API}/cities").json()
    assert len(cs) >= 2
    return cs


@pytest.fixture(scope="module")
def users(cities):
    """3 TEST customers: A1 (company A, city0), A2 (company A, city1), B1 (company B, city0)."""
    spec = [("a1", f"TEST_CoA {TAG}", cities[0]["id"]), ("a2", f"TEST_CoA {TAG}", cities[1]["id"]),
            ("b1", f"TEST_CoB {TAG}", cities[0]["id"])]
    out = {}
    for k, company, city in spec:
        email = f"test_{k}_{TAG}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "secret12", "phone": "0701234567",
                                                         "company": company, "name": f"TEST {k}", "city_id": city})
        assert r.status_code in (200, 201), r.text
        h = login(email, "secret12")
        me = requests.get(f"{API}/auth/me", headers=h).json()
        out[k] = {"h": h, "id": me["id"], "email": email, "company": company, "city": city}
    yield out
    ids = [u["id"] for u in out.values()]
    mdb.users.delete_many({"id": {"$in": ids}})
    mdb.notifications.delete_many({"user_id": {"$in": ids}})
    mdb.webpush_subs.delete_many({"user_id": {"$in": ids}})
    mdb.broadcasts.delete_many({"title": {"$regex": f"^TEST_.*{TAG}"}})


# --- PWA static assets
def test_pwa_assets():
    m = requests.get(f"{BASE_URL}/manifest.json")
    assert m.status_code == 200
    j = m.json()
    assert j["short_name"] == "Grit" and j["display"] == "standalone" and j["name"]
    srcs = {i["src"]: i for i in j["icons"]}
    assert "/icons/icon-192.png" in srcs and "/icons/icon-512.png" in srcs
    assert any(i.get("purpose") == "maskable" for i in j["icons"])
    for i in j["icons"]:
        r = requests.get(f"{BASE_URL}{i['src']}")
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/png")
    sw = requests.get(f"{BASE_URL}/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"] and "addEventListener(\"push\"" in sw.text
    assert requests.get(f"{BASE_URL}/icons/apple-touch-icon.png").status_code == 200
    html = requests.get(f"{BASE_URL}/").text
    assert 'rel="manifest"' in html and "apple-mobile-web-app-capable" in html and "viewport-fit=cover" in html


# --- Web push subscription API
def test_public_key():
    r = requests.get(f"{API}/webpush/public-key")
    assert r.status_code == 200
    k = r.json()["public_key"]
    raw = base64.urlsafe_b64decode(k + "=" * (-len(k) % 4))
    assert len(raw) == 65 and raw[0] == 4  # uncompressed P-256 point


def test_subscribe_requires_auth():
    r = requests.post(f"{API}/webpush/subscribe", json={"endpoint": "https://x.example/1", "keys": {"p256dh": "a", "auth": "b"}})
    assert r.status_code == 401


def test_subscribe_rejects_http(users):
    r = requests.post(f"{API}/webpush/subscribe", headers=users["a1"]["h"],
                      json={"endpoint": "http://x.example/1", "keys": {"p256dh": "a", "auth": "b"}})
    assert r.status_code == 400


def test_subscribe_upsert_and_unsubscribe(users):
    ep = f"https://fcm.example.test/TEST_{TAG}"
    h = users["a1"]["h"]
    for keys in ({"p256dh": "k1", "auth": "a1"}, {"p256dh": "k2", "auth": "a2"}):
        r = requests.post(f"{API}/webpush/subscribe", headers=h, json={"endpoint": ep, "keys": keys})
        assert r.status_code == 201 and r.json()["status"] == "subscribed"
    docs = list(mdb.webpush_subs.find({"endpoint": ep}, {"_id": 0}))
    assert len(docs) == 1 and docs[0]["keys"] == {"p256dh": "k2", "auth": "a2"} and docs[0]["user_id"] == users["a1"]["id"]
    # Another user cannot unsubscribe someone else's endpoint
    requests.post(f"{API}/webpush/unsubscribe", headers=users["b1"]["h"], json={"endpoint": ep})
    assert mdb.webpush_subs.count_documents({"endpoint": ep}) == 1
    r = requests.post(f"{API}/webpush/unsubscribe", headers=h, json={"endpoint": ep})
    assert r.status_code == 200 and r.json()["status"] == "unsubscribed"
    assert mdb.webpush_subs.count_documents({"endpoint": ep}) == 0


def test_subscribe_missing_keys_422(users):
    r = requests.post(f"{API}/webpush/subscribe", headers=users["a1"]["h"], json={"endpoint": "https://x.example/2"})
    assert r.status_code == 422


# --- Notification prefs
def test_prefs_default_and_persist(users):
    h = users["a2"]["h"]
    assert requests.get(f"{API}/notification-prefs").status_code == 401
    r = requests.get(f"{API}/notification-prefs", headers=h)
    assert r.status_code == 200 and r.json() == {"orders": True, "offers": True}
    r = requests.put(f"{API}/notification-prefs", headers=h, json={"orders": True, "offers": False})
    assert r.status_code == 200 and r.json() == {"orders": True, "offers": False}
    assert requests.get(f"{API}/notification-prefs", headers=h).json() == {"orders": True, "offers": False}
    assert mdb.users.find_one({"id": users["a2"]["id"]})["notify_prefs"] == {"orders": True, "offers": False}


# --- allowed_recipients unit test (in-process, hits same Mongo)
def test_allowed_recipients(users):
    sys.path.insert(0, "/app/backend")
    mdb.users.update_one({"id": users["b1"]["id"]}, {"$set": {"notify_prefs": {"orders": False, "offers": True}}})
    mdb.users.update_one({"id": users["a2"]["id"]}, {"$set": {"notify_prefs": {"orders": True, "offers": False}}})
    from routes.webpush import allowed_recipients
    ids = [users["a1"]["id"], users["a2"]["id"], users["b1"]["id"]]

    async def run():
        return await allowed_recipients(ids, "offers"), await allowed_recipients(ids, "orders")

    offers, orders = LOOP.run_until_complete(run())
    assert offers == [users["a1"]["id"], users["b1"]["id"]]
    assert orders == [users["a1"]["id"], users["a2"]["id"]]


# --- Admin broadcast targeting
def _bc(admin, **extra):
    body = {"title": f"TEST_bc {TAG}", "body": "TEST message", **extra}
    return requests.post(f"{API}/admin/broadcast", headers=admin, json=body)


def _got(u, title_tag=TAG):
    n = requests.get(f"{API}/notifications", headers=u["h"]).json()
    items = n if isinstance(n, list) else n.get("items", [])
    return [x for x in items if x.get("kind") == "broadcast" and title_tag in x.get("title", "")]


def test_broadcast_requires_admin(users):
    assert _bc(users["a1"]["h"]).status_code == 403


def test_broadcast_companies_only(admin, users):
    r = _bc(admin, companies=[users["a1"]["company"]])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["recipients"] == 2 and d["companies"] == [users["a1"]["company"]]
    assert len(_got(users["a1"])) == 1 and len(_got(users["a2"])) == 1 and len(_got(users["b1"])) == 0


def test_broadcast_companies_case_space_insensitive(admin, users):
    messy = "  " + users["b1"]["company"].lower().replace(" ", "   ") + " "
    r = _bc(admin, companies=[messy])
    assert r.status_code == 200 and r.json()["recipients"] == 1


def test_broadcast_companies_and_city(admin, users):
    r = _bc(admin, companies=[users["a1"]["company"], users["b1"]["company"]], city_id=users["a1"]["city"])
    assert r.status_code == 200
    assert r.json()["recipients"] == 2  # a1 + b1 (city0); a2 excluded by city


def test_broadcast_admins_excluded(admin, users):
    # Give an admin's company to check exclusion: use admin's company if present
    adm = mdb.users.find_one({"email": "admin@blaklader.local"})
    if not adm.get("company"):
        pytest.skip("admin has no company")
    r = _bc(admin, companies=[adm["company"]])
    assert r.status_code == 200
    ids = [u["id"] for u in mdb.users.find({"company": adm["company"], "role": {"$ne": "admin"}, "disabled": {"$ne": True}})]
    assert r.json()["recipients"] == len(ids)


def test_broadcast_unknown_company_zero(admin):
    r = _bc(admin, companies=[f"TEST_nonexistent {TAG}"])
    assert r.status_code == 200 and r.json()["recipients"] == 0


def test_broadcast_history_contains(admin):
    h = requests.get(f"{API}/admin/broadcasts", headers=admin).json()
    mine = [b for b in h if TAG in b["title"]]
    assert len(mine) >= 3 and all("_id" not in b for b in mine)


# --- send_webpush removes expired (410) subscriptions
def test_send_webpush_removes_gone_subscription(users):
    sys.path.insert(0, "/app/backend")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    pub = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    ep = "https://httpbin.org/status/410"
    try:
        requests.get(ep, timeout=8)
    except Exception:
        pytest.skip("httpbin unreachable")
    mdb.webpush_subs.delete_many({"endpoint": ep})
    mdb.webpush_subs.insert_one({"endpoint": ep, "keys": {"p256dh": b64(pub), "auth": b64(os.urandom(16))},
                                 "user_id": users["a1"]["id"]})
    from routes.webpush import send_webpush
    LOOP.run_until_complete(send_webpush([users["a1"]["id"]], "TEST", "TEST body", "/"))
    assert mdb.webpush_subs.count_documents({"endpoint": ep}) == 0
