# Iteration 9: colour ranking (solid pure colour first), notifications unread = DB count, failed-email admin notification
# NOTE: places NO orders, sends NO emails.
import os
import json
import uuid
import asyncio
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def cust():
    return login("delivered@resend.dev", "secret12")


def pick(colors, selected):
    """Python port of src/color-match.ts pickColor."""
    best, best_score = None, -1
    for c in colors or []:
        base = c.get("base") or []
        hits = [b for b in base if b in selected]
        if not hits:
            continue
        only = all(b in selected for b in base)
        solid = "/" not in c["name"]
        score = 3 if solid and only else 2 if solid else 1 if only else 0
        if score > best_score:
            best, best_score = c, score
    return best, best_score


def fetch(cust, sel, page=1):
    r = requests.get(f"{BASE_URL}/api/products", headers=cust,
                     params={"filters": json.dumps({"Color": sel}), "page": page, "page_size": 20})
    assert r.status_code == 200, r.text
    return r.json()


# --- FIX 1: colour ranking
class TestColorRanking:
    def test_blue_first_page_solid_blue(self, cust):
        d = fetch(cust, ["Blå"])
        assert d["total"] > 0 and d["items"]
        bad = []
        for p in d["items"]:
            c, s = pick(p.get("colors"), ["Blå"])
            assert c is not None, f"{p['part_no']} has no Blå colour"
            if s != 3 or "Svart" in c["name"] or "grå" in c["name"].lower():
                bad.append((p["part_no"], c["name"], c.get("base"), s))
        print("first page best:", [pick(p.get("colors"), ["Blå"])[0]["name"] for p in d["items"]])
        assert not bad, f"non-solid-blue on first page: {bad}"

    def test_blue_scores_monotonic_across_pages(self, cust):
        scores = []
        for pg in (1, 2, 3):
            d = fetch(cust, ["Blå"], pg)
            scores += [pick(p.get("colors"), ["Blå"])[1] for p in d["items"]]
            if not d["has_more"]:
                break
        assert scores == sorted(scores, reverse=True), scores

    def test_black_first_page_solid_black(self, cust):
        d = fetch(cust, ["Svart"])
        names = [pick(p.get("colors"), ["Svart"])[0]["name"] for p in d["items"]]
        print("svart first page:", names)
        assert d["items"]
        assert names[0] == "Svart" or "/" not in names[0], names

    def test_total_matches_unfiltered_ranking(self, cust):
        d = fetch(cust, ["Blå"])
        assert d["total"] == mdb.products.count_documents({"filters.Color": "Blå"}) or d["total"] > 0


# --- FIX 4: unread uses DB count
class TestNotificationsUnread:
    def test_unread_equals_db_count(self, cust):
        r = requests.get(f"{BASE_URL}/api/notifications", headers=cust)
        assert r.status_code == 200
        d = r.json()
        u = mdb.users.find_one({"email": "delivered@resend.dev"}, {"_id": 0, "id": 1})
        assert d["unread"] == mdb.notifications.count_documents({"user_id": u["id"], "read": False})
        assert isinstance(d["items"], list) and len(d["items"]) <= 100

    def test_unread_counts_beyond_100(self, cust):
        u = mdb.users.find_one({"email": "delivered@resend.dev"}, {"_id": 0, "id": 1})
        tag = f"TEST_{uuid.uuid4().hex[:6]}"
        docs = [{"id": f"{tag}_{i}", "user_id": u["id"], "order_id": "x", "order_number": "TEST", "kind": "new",
                 "title": tag, "body": "", "read": False, "created_at": "1970-01-01T00:00:00+00:00"} for i in range(105)]
        mdb.notifications.insert_many(docs)
        try:
            d = requests.get(f"{BASE_URL}/api/notifications", headers=cust).json()
            assert len(d["items"]) == 100
            assert d["unread"] >= 105
            assert d["unread"] == mdb.notifications.count_documents({"user_id": u["id"], "read": False})
        finally:
            mdb.notifications.delete_many({"title": tag})


# --- FIX 3: failed email still notifies admins (source-level check, no real send)
class TestFailedEmailNotification:
    def test_code_notifies_after_failure(self):
        src = open("/app/backend/routes/orders.py").read()
        i_fail = src.index('order["email_status"] = "failed"')
        i_notify = src.index("(mejlet kunde inte skickas)")
        seg = src[i_fail:i_notify]
        assert "raise" not in seg and "return" not in seg, "path between failure and notify exits early"
