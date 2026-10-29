# Blåkläder B2B ordering API regression tests (auth, cities, products, orders, admin)
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@blaklader.local", "password": "Admin123!"}
RECIPIENT = "delivered@resend.dev"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_h(s):
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def city(s):
    return s.get(f"{BASE_URL}/api/cities").json()[0]


@pytest.fixture(scope="module")
def customer(s, city, admin_h):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "Secret123", "phone": "0701234567", "company": "TEST_AB",
            "org_number": "556677-8899", "city_id": city["id"]}
    r = s.post(f"{BASE_URL}/api/auth/register", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    yield {"email": email, "pw": "Secret123", "id": d["user"]["id"], "user": d["user"],
           "h": {"Authorization": f"Bearer {d['access_token']}"}}
    s.delete(f"{BASE_URL}/api/admin/users/{d['user']['id']}", headers=admin_h)


# ---- auth
class TestAuth:
    def test_register_fields(self, customer, city):
        u = customer["user"]
        assert u["company"] == "TEST_AB" and u["role"] == "customer"
        assert u["city_name"] == city["name"] and u["org_number"] == "556677-8899"
        assert "password_hash" not in u

    def test_register_duplicate_409(self, s, customer, city):
        r = s.post(f"{BASE_URL}/api/auth/register", json={"email": customer["email"].upper(), "password": "Secret123",
                   "phone": "0701234567", "company": "X", "city_id": city["id"]})
        assert r.status_code == 409

    def test_register_invalid_city_400(self, s):
        r = s.post(f"{BASE_URL}/api/auth/register", json={"email": f"test_{uuid.uuid4().hex[:6]}@example.com",
                   "password": "Secret123", "phone": "0701234567", "company": "X", "city_id": "nope"})
        assert r.status_code == 400

    @pytest.mark.parametrize("patch", [{"email": "bad"}, {"password": "123"}, {"company": ""}, {"phone": "1"}])
    def test_register_validation_422(self, s, city, patch):
        body = {"email": f"test_{uuid.uuid4().hex[:6]}@example.com", "password": "Secret123",
                "phone": "0701234567", "company": "X", "city_id": city["id"], **patch}
        assert s.post(f"{BASE_URL}/api/auth/register", json=body).status_code == 422

    def test_login_wrong_pw_401(self, s, customer):
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": customer["email"], "password": "wrongpw"})
        assert r.status_code == 401

    def test_me(self, s, customer):
        r = s.get(f"{BASE_URL}/api/auth/me", headers=customer["h"])
        assert r.status_code == 200 and r.json()["email"] == customer["email"]
        assert s.get(f"{BASE_URL}/api/auth/me").status_code == 401


# ---- cities
class TestCities:
    def test_public_list(self, s):
        r = s.get(f"{BASE_URL}/api/cities")
        assert r.status_code == 200 and isinstance(r.json(), list) and "_id" not in r.json()[0]

    def test_non_admin_403(self, s, customer):
        assert s.post(f"{BASE_URL}/api/admin/cities", json={"name": "TEST_X"}, headers=customer["h"]).status_code == 403

    def test_crud(self, s, admin_h):
        name = f"TEST_City_{uuid.uuid4().hex[:4]}"
        r = s.post(f"{BASE_URL}/api/admin/cities", json={"name": name}, headers=admin_h)
        assert r.status_code == 200
        cid = r.json()["id"]
        assert s.post(f"{BASE_URL}/api/admin/cities", json={"name": name.lower()}, headers=admin_h).status_code == 409
        r = s.put(f"{BASE_URL}/api/admin/cities/{cid}", json={"name": name + "_R"}, headers=admin_h)
        assert r.status_code == 200
        names = [c["name"] for c in s.get(f"{BASE_URL}/api/cities").json()]
        assert name + "_R" in names
        assert s.delete(f"{BASE_URL}/api/admin/cities/{cid}", headers=admin_h).status_code == 200
        assert cid not in [c["id"] for c in s.get(f"{BASE_URL}/api/cities").json()]
        assert s.put(f"{BASE_URL}/api/admin/cities/{cid}", json={"name": "z"}, headers=admin_h).status_code == 404


# ---- products
class TestProducts:
    def test_list_paging(self, s, customer):
        r = s.get(f"{BASE_URL}/api/products", params={"page": 1, "page_size": 20}, headers=customer["h"])
        d = r.json()
        assert r.status_code == 200 and len(d["items"]) == 20 and d["total"] > 500 and d["has_more"]
        p2 = s.get(f"{BASE_URL}/api/products", params={"page": 2}, headers=customer["h"]).json()
        assert d["items"][0]["part_no"] != p2["items"][0]["part_no"]

    def test_search_and_category(self, s, customer):
        cats = s.get(f"{BASE_URL}/api/categories", headers=customer["h"]).json()
        assert len(cats) > 0
        g = cats[0]
        d = s.get(f"{BASE_URL}/api/products", params={"group": g["slug"]}, headers=customer["h"]).json()
        assert d["total"] == g["count"] and all(g["slug"] in i["groups"] for i in d["items"])
        q = s.get(f"{BASE_URL}/api/products", params={"q": "jacka"}, headers=customer["h"]).json()
        assert all("jacka" in i["name"].lower() or "jacka" in i["part_no"].lower() for i in q["items"])

    def test_detail_and_404(self, s, customer):
        pn = s.get(f"{BASE_URL}/api/products", headers=customer["h"]).json()["items"][0]["part_no"]
        r = s.get(f"{BASE_URL}/api/products/{pn}", headers=customer["h"])
        assert r.status_code == 200 and r.json()["part_no"] == pn and "colors" in r.json()
        assert s.get(f"{BASE_URL}/api/products/NOPE999", headers=customer["h"]).status_code == 404

    def test_requires_auth(self, s):
        assert s.get(f"{BASE_URL}/api/products").status_code == 401


# ---- orders + admin
class TestOrdersAdmin:
    def _item(self, s, h):
        p = s.get(f"{BASE_URL}/api/products", headers=h).json()["items"][0]
        p = s.get(f"{BASE_URL}/api/products/{p['part_no']}", headers=h).json()
        col = p["colors"][0]["code"] if p.get("colors") else None
        size = (p.get("sizes") or ["L"])[0]
        return {"part_no": p["part_no"], "color_code": col, "size": str(size), "quantity": 2}

    def test_settings_get_put(self, s, admin_h, customer):
        assert s.get(f"{BASE_URL}/api/admin/settings", headers=customer["h"]).status_code == 403
        assert s.put(f"{BASE_URL}/api/admin/settings", json={"order_email": "bad"}, headers=admin_h).status_code == 422
        r = s.put(f"{BASE_URL}/api/admin/settings", json={"order_email": RECIPIENT}, headers=admin_h)
        assert r.status_code == 200
        g = s.get(f"{BASE_URL}/api/admin/settings", headers=admin_h).json()
        assert g["order_email"] == RECIPIENT and g["product_count"] > 500

    def test_create_order_and_email(self, s, customer, admin_h):
        it = self._item(s, customer["h"])
        r = s.post(f"{BASE_URL}/api/orders", json={"items": [it], "comment": "TEST leverans v.12"}, headers=customer["h"])
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["email_status"] == "sent" and o["order_number"].startswith("B")
        assert o["items"][0]["quantity"] == 2 and o["customer"]["company"] == "TEST_AB"
        mine = s.get(f"{BASE_URL}/api/orders", headers=customer["h"]).json()
        assert [x["id"] for x in mine] == [o["id"]]
        allo = s.get(f"{BASE_URL}/api/admin/orders", headers=admin_h).json()
        assert o["id"] in [x["id"] for x in allo]

    def test_order_validation(self, s, customer):
        assert s.post(f"{BASE_URL}/api/orders", json={"items": []}, headers=customer["h"]).status_code == 422
        bad = {"items": [{"part_no": "NOPE", "size": "L", "quantity": 1}]}
        assert s.post(f"{BASE_URL}/api/orders", json=bad, headers=customer["h"]).status_code == 400

    def test_order_503_without_recipient(self, s, customer, admin_h):
        import pymongo
        from dotenv import dotenv_values
        env = dotenv_values("/app/backend/.env")
        col = pymongo.MongoClient(env["MONGO_URL"])[env["DB_NAME"]].settings
        col.update_one({"id": "global"}, {"$unset": {"order_email": ""}})
        try:
            r = s.post(f"{BASE_URL}/api/orders", json={"items": [self._item(s, customer["h"])]}, headers=customer["h"])
            assert r.status_code == 503
        finally:
            col.update_one({"id": "global"}, {"$set": {"order_email": RECIPIENT}}, upsert=True)

    def test_admin_users(self, s, admin_h, customer, city):
        lst = s.get(f"{BASE_URL}/api/admin/users", params={"q": "TEST_AB"}, headers=admin_h).json()
        assert customer["id"] in [u["id"] for u in lst] and all("password_hash" not in u for u in lst)
        d = s.get(f"{BASE_URL}/api/admin/users/{customer['id']}", headers=admin_h).json()
        assert d["order_count"] >= 1
        r = s.put(f"{BASE_URL}/api/admin/users/{customer['id']}", json={"company": "TEST_AB2", "phone": "0709999999"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["company"] == "TEST_AB2"
        assert s.put(f"{BASE_URL}/api/admin/users/{customer['id']}", json={"role": "boss"}, headers=admin_h).status_code == 400
        assert s.put(f"{BASE_URL}/api/admin/users/{customer['id']}", json={"city_id": "nope"}, headers=admin_h).status_code == 400

    def test_disable_blocks_login(self, s, admin_h, customer):
        s.put(f"{BASE_URL}/api/admin/users/{customer['id']}", json={"disabled": True}, headers=admin_h)
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": customer["email"], "password": customer["pw"]})
        assert r.status_code == 403
        assert s.get(f"{BASE_URL}/api/auth/me", headers=customer["h"]).status_code == 401
        s.put(f"{BASE_URL}/api/admin/users/{customer['id']}", json={"disabled": False}, headers=admin_h)

    def test_admin_self_protection(self, s, admin_h):
        me = s.get(f"{BASE_URL}/api/auth/me", headers=admin_h).json()
        assert s.put(f"{BASE_URL}/api/admin/users/{me['id']}", json={"disabled": True}, headers=admin_h).status_code == 400
        assert s.delete(f"{BASE_URL}/api/admin/users/{me['id']}", headers=admin_h).status_code == 400

    def test_delete_user(self, s, admin_h, city):
        r = s.post(f"{BASE_URL}/api/auth/register", json={"email": f"test_{uuid.uuid4().hex[:6]}@example.com",
                   "password": "Secret123", "phone": "0701234567", "company": "TEST_DEL", "city_id": city["id"]})
        uid = r.json()["user"]["id"]
        assert s.delete(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_h).status_code == 200
        assert s.get(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_h).status_code == 404

    def test_catalog_sync_forbidden_for_customer(self, s, customer):
        assert s.post(f"{BASE_URL}/api/admin/catalog/sync", headers=customer["h"]).status_code == 403
