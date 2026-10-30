# Seed a UI test customer (delivered+ui13@resend.dev / secret12) with 4 orders (new/confirmed/declined/ready) + 1 favourite.
# Usage: python seed_iter13_ui.py [cleanup]
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
API = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") + "/api"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
EMAIL = "delivered+ui13@resend.dev"


def cleanup():
    u = mdb.users.find_one({"email": EMAIL})
    if u:
        mdb.orders.delete_many({"user_id": u["id"]})
        mdb.notifications.delete_many({"user_id": u["id"]})
        mdb.favorites.delete_many({"user_id": u["id"]})
        mdb.users.delete_one({"id": u["id"]})
    mdb.notifications.delete_many({"order_number": {"$regex": "^UI13"}})
    mdb.companies.delete_many({"name": "TEST_UI13 Bygg"})
    print("cleaned")


if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    cleanup()
    sys.exit()

cleanup()
cities = requests.get(f"{API}/cities").json()
r = requests.post(f"{API}/auth/register", json={"email": EMAIL, "password": "secret12", "phone": "07011111",
                                                "company": "TEST_UI13 Bygg", "city_id": cities[0]["id"]})
assert r.status_code == 200, r.text
user = r.json()["user"]
h = {"Authorization": f"Bearer {r.json()['access_token']}"}
p = mdb.products.find_one({"sizes.0": {"$exists": True}, "colors.0": {"$exists": True}, "hidden_city_ids": {"$ne": cities[0]["id"]}}, {"_id": 0})
requests.post(f"{API}/favorites", headers=h, json={"part_no": p["part_no"], "color_code": p["colors"][0]["code"]})
now = datetime.now(timezone.utc)
for i, st in enumerate(["new", "confirmed", "declined", "ready"]):
    t = (now - timedelta(minutes=10 * (4 - i))).isoformat()
    replies = []
    if st in ("confirmed", "ready"):
        replies = [{"message": "Levereras torsdag", "created_at": t, "action": "confirm"}]
    if st == "declined":
        replies = [{"message": "Slut i lager", "created_at": t, "action": "decline"}]
    o = {"id": str(uuid.uuid4()), "order_number": f"UI13{st[:3].upper()}", "user_id": user["id"],
         "customer": {"email": EMAIL, "company": "TEST_UI13 Bygg", "phone": "", "org_number": "", "city_name": cities[0]["name"]},
         "items": [{"part_no": p["part_no"], "name": p["name"], "size": p["sizes"][0], "quantity": i + 1,
                    "color_code": p["colors"][0]["code"], "color_name": p["colors"][0]["name"], "image_url": p.get("image_url")}],
         "comment": "", "delivery": {"method": "store"}, "order_value": 0, "created_at": t, "email_status": "sent",
         "sent_to": "x@resend.dev", "status": st, "confirm_token": uuid.uuid4().hex + uuid.uuid4().hex, "replies": replies}
    if st == "ready":
        o["ready_at"] = now.isoformat()
    mdb.orders.insert_one(o)
print("seeded", user["id"], p["part_no"])
