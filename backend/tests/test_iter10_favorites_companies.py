# Iteration 10: favourites (per-user, dedupe, validation), company grouping, company-users, company normalisation on PUT
# NOTE: places NO orders, sends NO emails.
import os
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = uuid.uuid4().hex[:6]


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@blaklader.local", "Admin123!")


@pytest.fixture(scope="module")
def city_id():
    return requests.get(f"{BASE_URL}/api/cities").json()[0]["id"]


@pytest.fixture(scope="module")
def users(admin, city_id):
    """Create 3 TEST_ customers with same company in different spellings."""
    spellings = [f"TEST_Patriks Bygg {TAG}", f"test_patriks  bygg {TAG}", f"  TEST_PATRIKS BYGG {TAG} "]
    created = []
    for i, comp in enumerate(spellings):
        email = f"test_{TAG}_{i}@example.com"
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=admin, json={
            "email": email, "password": "secret12", "phone": "0701234567", "company": comp, "city_id": city_id})
        assert r.status_code == 200, r.text
        created.append({**r.json(), "email": email})
    yield created
    for u in created:
        requests.delete(f"{BASE_URL}/api/admin/users/{u['id']}", headers=admin)
        mdb.favorites.delete_many({"user_id": u["id"]})


@pytest.fixture(scope="module")
def product():
    p = mdb.products.find_one({"active": {"$ne": False}, "colors.1": {"$exists": True}}, {"_id": 0, "part_no": 1, "colors": 1})
    assert p
    return p


# ---- favourites
class TestFavorites:
    def test_auth_required(self):
        assert requests.get(f"{BASE_URL}/api/favorites").status_code in (401, 403)
        assert requests.post(f"{BASE_URL}/api/favorites", json={"part_no": "x"}).status_code in (401, 403)

    def test_add_dedupe_list_delete(self, users, product):
        h = login(users[0]["email"], "secret12")
        c0, c1 = product["colors"][0], product["colors"][1]
        r1 = requests.post(f"{BASE_URL}/api/favorites", headers=h, json={"part_no": product["part_no"], "color_code": c0["code"]})
        assert r1.status_code == 200, r1.text
        f1 = r1.json()
        assert f1["part_no"] == product["part_no"] and f1["color_code"] == c0["code"] and f1["color_name"] == c0["name"]
        assert "user_id" not in f1 and "_id" not in f1 and f1.get("image_url")
        # dedupe
        r2 = requests.post(f"{BASE_URL}/api/favorites", headers=h, json={"part_no": product["part_no"], "color_code": c0["code"]})
        assert r2.status_code == 200 and r2.json()["id"] == f1["id"]
        # other colour = separate fav
        r3 = requests.post(f"{BASE_URL}/api/favorites", headers=h, json={"part_no": product["part_no"], "color_code": c1["code"]})
        assert r3.status_code == 200 and r3.json()["id"] != f1["id"]
        lst = requests.get(f"{BASE_URL}/api/favorites", headers=h).json()
        assert len(lst) == 2 and {f["color_code"] for f in lst} == {c0["code"], c1["code"]}
        # per-user isolation
        h2 = login(users[1]["email"], "secret12")
        assert requests.get(f"{BASE_URL}/api/favorites", headers=h2).json() == []
        # other user cannot delete
        requests.delete(f"{BASE_URL}/api/favorites/{f1['id']}", headers=h2)
        assert len(requests.get(f"{BASE_URL}/api/favorites", headers=h).json()) == 2
        # delete
        d = requests.delete(f"{BASE_URL}/api/favorites/{f1['id']}", headers=h)
        assert d.status_code == 200
        lst = requests.get(f"{BASE_URL}/api/favorites", headers=h).json()
        assert [f["id"] for f in lst] == [r3.json()["id"]]

    def test_unknown_product_404(self, users):
        h = login(users[0]["email"], "secret12")
        r = requests.post(f"{BASE_URL}/api/favorites", headers=h, json={"part_no": "NOPE_" + TAG, "color_code": "1"})
        assert r.status_code == 404

    def test_unknown_color_400(self, users, product):
        h = login(users[0]["email"], "secret12")
        r = requests.post(f"{BASE_URL}/api/favorites", headers=h, json={"part_no": product["part_no"], "color_code": "ZZZZ"})
        assert r.status_code == 400

    def test_no_color_allowed(self, users, product):
        h = login(users[2]["email"], "secret12")
        r = requests.post(f"{BASE_URL}/api/favorites", headers=h, json={"part_no": product["part_no"]})
        assert r.status_code == 200 and r.json()["color_code"] is None


# ---- companies
class TestCompanies:
    def test_admin_only(self, users):
        h = login(users[0]["email"], "secret12")
        assert requests.get(f"{BASE_URL}/api/admin/companies", headers=h).status_code == 403
        assert requests.get(f"{BASE_URL}/api/admin/company-users", headers=h, params={"name": "x"}).status_code == 403

    def test_grouping(self, admin, users):
        lst = requests.get(f"{BASE_URL}/api/admin/companies", headers=admin).json()
        key = f"test_patriks bygg {TAG}"
        g = [c for c in lst if c["key"] == key]
        assert len(g) == 1, [c for c in lst if TAG in c["key"]]
        g = g[0]
        assert g["count"] == 3
        assert set(g.keys()) >= {"key", "name", "count", "spellings"}
        assert all("  " not in s and s == s.strip() for s in g["spellings"])

    def test_company_users_insensitive(self, admin, users):
        r = requests.get(f"{BASE_URL}/api/admin/company-users", headers=admin, params={"name": f"  tEsT_PATRIKS   bygg {TAG}"})
        assert r.status_code == 200
        ids = {u["id"] for u in r.json()}
        assert ids == {u["id"] for u in users}
        assert all("password_hash" not in u for u in r.json())

    def test_company_users_empty_name(self, admin):
        assert requests.get(f"{BASE_URL}/api/admin/company-users", headers=admin, params={"name": "   "}).status_code == 400

    def test_put_company_normalises(self, admin, users):
        uid = users[2]["id"]
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}", headers=admin, json={"company": f"  TEST_Patriks    Bygg {TAG}  "})
        assert r.status_code == 200 and r.json()["company"] == f"TEST_Patriks Bygg {TAG}"
        got = requests.get(f"{BASE_URL}/api/admin/users/{uid}", headers=admin).json()
        assert got["company"] == f"TEST_Patriks Bygg {TAG}"

    def test_put_empty_company_rejected(self, admin, users):
        r = requests.put(f"{BASE_URL}/api/admin/users/{users[2]['id']}", headers=admin, json={"company": "   "})
        assert r.status_code == 400
