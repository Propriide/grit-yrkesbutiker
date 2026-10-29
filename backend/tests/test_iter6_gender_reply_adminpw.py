# Iteration 6: gender filter, colors[].base, admin in-app order reply, admin set user password
import json
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@blaklader.local", "password": "Admin123!"}
CUSTOMER = {"email": "delivered@resend.dev", "password": "secret12"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
    if r.status_code != 200:
        pytest.skip(f"login failed {creds['email']} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_h():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def cust_h():
    return _login(CUSTOMER)


def _total(h, **params):
    r = requests.get(f"{BASE_URL}/api/products", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# --- Gender filter
class TestGender:
    def test_totals(self, cust_h):
        allp = _total(cust_h)["total"]
        herr = _total(cust_h, gender="herr")["total"]
        dam = _total(cust_h, gender="dam")["total"]
        print("all/herr/dam", allp, herr, dam)
        assert allp > herr > dam > 0
        assert abs(herr - 971) < 60 and abs(dam - 565) < 60

    def test_gender_items_match(self, cust_h):
        items = _total(cust_h, gender="dam", page_size=60)["items"]
        for p in items:
            g = p.get("gender") or []
            assert not g or "Dam" in g or "Unisex" in g, (p["part_no"], g)

    def test_gender_with_group_and_filters(self, cust_h):
        cats = requests.get(f"{BASE_URL}/api/categories", headers=cust_h).json()
        grp = cats[0]["slug"]
        g_all = _total(cust_h, group=grp)["total"]
        g_dam = _total(cust_h, group=grp, gender="dam")["total"]
        assert g_dam <= g_all
        f = json.dumps({"Color": ["Svart"]})
        f_all = _total(cust_h, filters=f)["total"]
        f_herr = _total(cust_h, filters=f, gender="herr")["total"]
        assert 0 < f_herr <= f_all
        q_herr = _total(cust_h, q="byxa", gender="herr")
        assert q_herr["total"] >= 0

    def test_categories_and_filters_counts_change(self, cust_h):
        ca = requests.get(f"{BASE_URL}/api/categories", headers=cust_h).json()
        cd = requests.get(f"{BASE_URL}/api/categories", headers=cust_h, params={"gender": "dam"}).json()
        assert sum(c["count"] for c in cd) < sum(c["count"] for c in ca)
        fa = requests.get(f"{BASE_URL}/api/filters", headers=cust_h).json()
        fh = requests.get(f"{BASE_URL}/api/filters", headers=cust_h, params={"gender": "herr"}).json()
        ca_c = {v["value"]: v["count"] for f in fa if f["code"] == "Color" for v in f["values"]}
        ch_c = {v["value"]: v["count"] for f in fh if f["code"] == "Color" for v in f["values"]}
        assert ch_c.get("Svart", 0) < ca_c.get("Svart", 0)

    def test_colors_base(self, cust_h):
        items = _total(cust_h, page_size=60)["items"]
        with_colors = [p for p in items if p.get("colors")]
        assert with_colors
        for p in with_colors:
            for c in p["colors"]:
                assert isinstance(c.get("base"), list)
        assert any("Svart" in c["base"] for p in with_colors for c in p["colors"])


# --- Admin in-app order reply
class TestAdminReply:
    @pytest.fixture(scope="class")
    def order(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        orders = data if isinstance(data, list) else data.get("items", data.get("orders", []))
        cand = [o for o in orders if o["customer"]["email"] == "delivered@resend.dev" and o.get("status") == "new"]
        if not cand:
            pytest.skip("no new order by delivered@resend.dev")
        return cand[0]

    def test_customer_forbidden(self, cust_h, order):
        r = requests.post(f"{BASE_URL}/api/admin/orders/{order['id']}/reply", headers=cust_h, json={"message": "hej"})
        assert r.status_code == 403

    def test_unknown_404(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/admin/orders/{uuid.uuid4()}/reply", headers=admin_h, json={"message": "hej"})
        assert r.status_code == 404

    def test_empty_422(self, admin_h, order):
        r = requests.post(f"{BASE_URL}/api/admin/orders/{order['id']}/reply", headers=admin_h, json={"message": ""})
        assert r.status_code == 422
        r = requests.post(f"{BASE_URL}/api/admin/orders/{order['id']}/reply", headers=admin_h, json={"message": "   "})
        assert r.status_code in (400, 422)

    def test_forbidden_word_400(self, admin_h, order):
        r = requests.post(f"{BASE_URL}/api/admin/orders/{order['id']}/reply", headers=admin_h,
                          json={"message": "Ange din cvv kod"})
        assert r.status_code == 400
        assert "otillåtna" in r.json()["detail"]

    def test_reply_confirms(self, admin_h, order):
        msg = f"TEST_ Leverans på fredag {uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/admin/orders/{order['id']}/reply", headers=admin_h, json={"message": msg})
        if r.status_code == 400 and "kunde inte skickas" in r.text:
            pytest.skip("email provider rate-limited")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "confirmed"
        assert d["replies"][-1]["message"] == msg
        assert "confirm_token" not in d and "_id" not in d


# --- Admin set user password
class TestAdminPassword:
    @pytest.fixture(scope="class")
    def throwaway(self, admin_h):
        email = f"test_pw_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=admin_h,
                          json={"email": email, "password": "orig123", "company": "TEST_ AB"})
        assert r.status_code == 200, r.text
        u = r.json()
        yield {"id": u["id"], "email": email}
        requests.delete(f"{BASE_URL}/api/admin/users/{u['id']}", headers=admin_h)

    def test_customer_forbidden(self, cust_h, throwaway):
        r = requests.put(f"{BASE_URL}/api/admin/users/{throwaway['id']}/password", headers=cust_h,
                         json={"new_password": "newpass1"})
        assert r.status_code == 403

    def test_short_422(self, admin_h, throwaway):
        r = requests.put(f"{BASE_URL}/api/admin/users/{throwaway['id']}/password", headers=admin_h,
                         json={"new_password": "abc"})
        assert r.status_code == 422

    def test_unknown_404(self, admin_h):
        r = requests.put(f"{BASE_URL}/api/admin/users/{uuid.uuid4()}/password", headers=admin_h,
                         json={"new_password": "newpass1"})
        assert r.status_code == 404

    def test_set_and_login(self, admin_h, throwaway):
        r = requests.put(f"{BASE_URL}/api/admin/users/{throwaway['id']}/password", headers=admin_h,
                         json={"new_password": "newpass1"})
        assert r.status_code == 200 and r.json()["ok"] is True
        ok = requests.post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "newpass1"})
        assert ok.status_code == 200 and "access_token" in ok.json()
        old = requests.post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "orig123"})
        assert old.status_code == 401
