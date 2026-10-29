# Iteration 5: admin create user, profile edit, change password, forgot/reset password, color filter
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@blaklader.local", "password": "Admin123!"}
CUSTOMER = {"email": "delivered@resend.dev", "password": "secret12"}


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
        pytest.skip(f"login failed {creds['email']} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_h():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def cust_h():
    return _login(CUSTOMER)


@pytest.fixture(scope="module")
def city_id(admin_h):
    cities = requests.get(f"{BASE_URL}/api/cities").json()
    return cities[0]["id"] if cities else None


@pytest.fixture(scope="module")
def created(admin_h, db):
    ids = []
    yield ids
    for uid in ids:
        requests.delete(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_h)
    db.password_resets.delete_many({"email": {"$regex": "^test_iter5_"}})
    db.login_attempts.delete_many({"email": {"$regex": "^test_iter5_"}})


def _new_user(admin_h, created, city_id, role="customer"):
    email = f"test_iter5_{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "Passw0rd!", "phone": "0701234567", "company": "TEST_Firma AB",
            "org_number": "556677-8899", "city_id": city_id, "role": role}
    r = requests.post(f"{BASE_URL}/api/admin/users", json=body, headers=admin_h)
    assert r.status_code == 200, r.text
    u = r.json()
    created.append(u["id"])
    return email, u


# --- Admin create user
class TestAdminCreateUser:
    def test_create_and_login(self, admin_h, created, city_id):
        email, u = _new_user(admin_h, created, city_id)
        assert u["email"] == email and u["role"] == "customer" and u["company"] == "TEST_Firma AB"
        assert u["org_number"] == "556677-8899" and u["city_id"] == city_id
        assert "password_hash" not in u
        g = requests.get(f"{BASE_URL}/api/admin/users/{u['id']}", headers=admin_h)
        assert g.status_code == 200 and g.json()["email"] == email
        lst = requests.get(f"{BASE_URL}/api/admin/users", params={"q": email}, headers=admin_h).json()
        assert any(x["id"] == u["id"] for x in lst)
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Passw0rd!"})
        assert r.status_code == 200 and r.json()["user"]["role"] == "customer"

    def test_create_admin_role_works(self, admin_h, created, city_id):
        email, u = _new_user(admin_h, created, city_id, role="admin")
        assert u["role"] == "admin"
        h = _login({"email": email, "password": "Passw0rd!"})
        assert requests.get(f"{BASE_URL}/api/admin/users", headers=h).status_code == 200

    def test_customer_forbidden(self, cust_h):
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=cust_h,
                          json={"email": "test_iter5_x@example.com", "password": "Passw0rd!", "company": "X"})
        assert r.status_code == 403

    def test_duplicate_409(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=admin_h,
                          json={"email": "DELIVERED@resend.dev", "password": "Passw0rd!", "company": "X"})
        assert r.status_code == 409

    def test_invalid_city_and_role_400(self, admin_h):
        base = {"email": f"test_iter5_{uuid.uuid4().hex[:6]}@example.com", "password": "Passw0rd!", "company": "X"}
        assert requests.post(f"{BASE_URL}/api/admin/users", headers=admin_h, json={**base, "city_id": "nope"}).status_code == 400
        assert requests.post(f"{BASE_URL}/api/admin/users", headers=admin_h, json={**base, "role": "superuser"}).status_code == 400

    def test_promote_existing_to_admin(self, admin_h, created, city_id):
        email, u = _new_user(admin_h, created, city_id)
        r = requests.put(f"{BASE_URL}/api/admin/users/{u['id']}", json={"role": "admin"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["role"] == "admin"
        h = _login({"email": email, "password": "Passw0rd!"})
        assert requests.get(f"{BASE_URL}/api/admin/settings", headers=h).status_code == 200


# --- Profile edit
class TestProfileEdit:
    def test_update_me(self, admin_h, created, city_id):
        email, _ = _new_user(admin_h, created, city_id)
        h = _login({"email": email, "password": "Passw0rd!"})
        r = requests.put(f"{BASE_URL}/api/auth/me", headers=h,
                         json={"company": "TEST_Nytt AB", "phone": "0709999999", "org_number": "111111-2222", "city_id": city_id})
        assert r.status_code == 200 and r.json()["company"] == "TEST_Nytt AB"
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=h).json()
        assert me["company"] == "TEST_Nytt AB" and me["phone"] == "0709999999" and me["org_number"] == "111111-2222"
        assert me["role"] == "customer" and me["email"] == email

    def test_update_me_validation(self, admin_h, created, city_id):
        email, _ = _new_user(admin_h, created, city_id)
        h = _login({"email": email, "password": "Passw0rd!"})
        assert requests.put(f"{BASE_URL}/api/auth/me", headers=h, json={"company": "", "phone": "0701234567"}).status_code == 422
        assert requests.put(f"{BASE_URL}/api/auth/me", headers=h,
                            json={"company": "A", "phone": "0701234567", "city_id": "bad"}).status_code == 400
        # cannot escalate role via profile update
        requests.put(f"{BASE_URL}/api/auth/me", headers=h, json={"company": "A", "phone": "0701234567", "role": "admin"})
        assert requests.get(f"{BASE_URL}/api/auth/me", headers=h).json()["role"] == "customer"

    def test_update_me_unauth(self):
        assert requests.put(f"{BASE_URL}/api/auth/me", json={"company": "A", "phone": "0701234567"}).status_code == 401


# --- Change password
class TestChangePassword:
    def test_change_password(self, admin_h, created, city_id):
        email, _ = _new_user(admin_h, created, city_id)
        h = _login({"email": email, "password": "Passw0rd!"})
        r = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                          json={"current_password": "wrongpass", "new_password": "NewPass1!"})
        assert r.status_code == 400
        r = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                          json={"current_password": "Passw0rd!", "new_password": "123"})
        assert r.status_code == 422
        r = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                          json={"current_password": "Passw0rd!", "new_password": "NewPass1!"})
        assert r.status_code == 200 and r.json()["ok"] is True
        assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "NewPass1!"}).status_code == 200
        assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Passw0rd!"}).status_code == 401


# --- Forgot / reset password
class TestForgotReset:
    def test_forgot_neutral(self, db, admin_h, created, city_id):
        r1 = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "test_iter5_unknown@example.com"})
        email, _ = _new_user(admin_h, created, city_id)
        r2 = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email})
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()
        rec = db.password_resets.find_one({"email": email})
        assert rec and rec["code_hash"].startswith("$2") and rec["attempts"] == 0
        assert db.password_resets.count_documents({"email": "test_iter5_unknown@example.com"}) == 0

    def test_wrong_code_and_lockout(self, db, admin_h, created, city_id):
        email, _ = _new_user(admin_h, created, city_id)
        now = datetime.now(timezone.utc)
        db.password_resets.insert_one({"email": email, "code_hash": bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode(),
                                       "attempts": 0, "created_at": now.isoformat(),
                                       "expires_at": (now + timedelta(minutes=15)).isoformat(),
                                       "expire_at": now + timedelta(minutes=15)})
        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": "000000", "new_password": "Reset123!"})
            assert r.status_code == 400
        assert db.password_resets.find_one({"email": email})["attempts"] == 5
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": "123456", "new_password": "Reset123!"})
        assert r.status_code == 400
        assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Passw0rd!"}).status_code == 200

    def test_reset_happy_path(self, db, admin_h, created, city_id):
        email, _ = _new_user(admin_h, created, city_id)
        now = datetime.now(timezone.utc)
        db.password_resets.insert_one({"email": email, "code_hash": bcrypt.hashpw(b"654321", bcrypt.gensalt()).decode(),
                                       "attempts": 0, "created_at": now.isoformat(),
                                       "expires_at": (now + timedelta(minutes=15)).isoformat(),
                                       "expire_at": now + timedelta(minutes=15)})
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email.upper(), "code": "654321", "new_password": "Reset123!"})
        assert r.status_code == 200 and r.json()["ok"] is True
        assert db.password_resets.count_documents({"email": email}) == 0
        assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Reset123!"}).status_code == 200
        # code cannot be reused
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": "654321", "new_password": "Other123!"})
        assert r.status_code == 400

    def test_expired_code_rejected(self, db, admin_h, created, city_id):
        email, _ = _new_user(admin_h, created, city_id)
        now = datetime.now(timezone.utc)
        db.password_resets.insert_one({"email": email, "code_hash": bcrypt.hashpw(b"111222", bcrypt.gensalt()).decode(),
                                       "attempts": 0, "created_at": (now - timedelta(minutes=20)).isoformat(),
                                       "expires_at": (now - timedelta(minutes=5)).isoformat(),
                                       "expire_at": now + timedelta(minutes=5)})
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": "111222", "new_password": "Reset123!"})
        assert r.status_code == 400


# --- Color filter
class TestColorFilter:
    def test_color_filter_reduces(self, cust_h):
        f = requests.get(f"{BASE_URL}/api/filters", headers=cust_h).json()
        color = next((x for x in f if x["code"] == "Color"), None)
        assert color is not None, [x["code"] for x in f]
        names = [v["value"] for v in color["values"]]
        assert "Svart" in names
        total = requests.get(f"{BASE_URL}/api/products", headers=cust_h).json()["total"]
        sv = requests.get(f"{BASE_URL}/api/products", params={"filters": json.dumps({"Color": ["Svart"]})}, headers=cust_h).json()
        print("total", total, "svart", sv["total"], "names", names[:10])
        assert 0 < sv["total"] < total
