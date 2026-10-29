# Iteration 11: admin company-orders + per-user orders endpoints
# NOTE: places NO orders via API (no emails). TEST_ orders are inserted directly in Mongo and cleaned up.
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
COMPANY = f"TEST_Order Bygg {TAG}"


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def customer():
    return login("delivered@resend.dev", "secret12")


@pytest.fixture(scope="module")
def setup(admin):
    city = requests.get(f"{BASE_URL}/api/cities").json()[0]["id"]
    spellings = [COMPANY, f"  test_order   bygg {TAG.upper()} "]
    users = []
    for i, comp in enumerate(spellings):
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=admin, json={
            "email": f"test_o_{TAG}_{i}@example.com", "password": "secret12", "phone": "070", "company": comp, "city_id": city})
        assert r.status_code == 200, r.text
        users.append(r.json())
    base = datetime.now(timezone.utc)
    orders = []
    # u0: 2 orders, u1: 1 order, orphan order (user deleted) with customer.company match, unrelated order
    plan = [(users[0]["id"], COMPANY, 0), (users[0]["id"], COMPANY, 1), (users[1]["id"], spellings[1], 2),
            ("deleted-" + TAG, COMPANY.lower(), 3), ("other-" + TAG, f"TEST_Other {TAG}", 4)]
    for uid, comp, i in plan:
        o = {"id": str(uuid.uuid4()), "order_number": f"TEST{TAG}{i}", "user_id": uid,
             "customer": {"email": "x@example.com", "company": comp, "phone": "", "org_number": "", "city_name": "X"},
             "items": [], "comment": "", "created_at": (base + timedelta(seconds=i)).isoformat(),
             "status": "sent", "email_status": "sent", "confirm_token": "secret-tok", "replies": []}
        mdb.orders.insert_one(dict(o))
        orders.append(o)
    yield {"users": users, "orders": orders}
    mdb.orders.delete_many({"order_number": {"$regex": f"^TEST{TAG}"}})
    for u in users:
        requests.delete(f"{BASE_URL}/api/admin/users/{u['id']}", headers=admin)


# --- company orders
class TestCompanyOrders:
    def test_company_orders_includes_all(self, admin, setup):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": COMPANY})
        assert r.status_code == 200, r.text
        nums = [o["order_number"] for o in r.json()]
        assert set(nums) == {f"TEST{TAG}{i}" for i in range(4)}, nums
        # sorted desc by created_at
        assert nums == [f"TEST{TAG}{i}" for i in (3, 2, 1, 0)]

    def test_company_orders_case_space_insensitive(self, admin, setup):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": f"  test_ORDER    bygg   {TAG} "})
        assert r.status_code == 200
        assert len(r.json()) == 4

    def test_no_internal_fields(self, admin, setup):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": COMPANY})
        for o in r.json():
            assert "_id" not in o and "confirm_token" not in o

    def test_company_orders_no_partial_match(self, admin, setup):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": "TEST_Order"})
        assert r.status_code == 200
        assert not any(o["order_number"].startswith(f"TEST{TAG}") for o in r.json())

    def test_company_orders_regex_chars_safe(self, admin):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": ".*"})
        assert r.status_code == 200 and r.json() == []

    def test_empty_name_400(self, admin):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": "   "})
        assert r.status_code == 400

    def test_missing_name_422(self, admin):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin)
        assert r.status_code == 422

    def test_customer_forbidden(self, customer):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=customer, params={"name": "Testbygg AB"})
        assert r.status_code == 403

    def test_unauth(self):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", params={"name": "Testbygg AB"})
        assert r.status_code in (401, 403)

    def test_seeded_patriks_bygg_has_b10035(self, admin):
        r = requests.get(f"{BASE_URL}/api/admin/company-orders", headers=admin, params={"name": "patriks BYGG"})
        assert r.status_code == 200
        assert "B10035" in [o["order_number"] for o in r.json()]


# --- per-user orders
class TestUserOrders:
    def test_user_orders(self, admin, setup):
        u0 = setup["users"][0]["id"]
        r = requests.get(f"{BASE_URL}/api/admin/users/{u0}/orders", headers=admin)
        assert r.status_code == 200
        data = r.json()
        assert [o["order_number"] for o in data] == [f"TEST{TAG}1", f"TEST{TAG}0"]
        assert all(o["user_id"] == u0 and "confirm_token" not in o and "_id" not in o for o in data)

    def test_user_order_count_matches(self, admin, setup):
        u1 = setup["users"][1]["id"]
        cnt = requests.get(f"{BASE_URL}/api/admin/users/{u1}", headers=admin).json()["order_count"]
        lst = requests.get(f"{BASE_URL}/api/admin/users/{u1}/orders", headers=admin).json()
        assert cnt == len(lst) == 1

    def test_unknown_user_empty(self, admin):
        r = requests.get(f"{BASE_URL}/api/admin/users/nope-{TAG}/orders", headers=admin)
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json() == []

    def test_customer_forbidden(self, customer, setup):
        r = requests.get(f"{BASE_URL}/api/admin/users/{setup['users'][0]['id']}/orders", headers=customer)
        assert r.status_code == 403
