# Iter14 UI seed on top of seed_iter13_ui.py: saved addresses for delivered+ui13 and admin 'new' notification for UI13NEW.
# Usage: python seed_iter14_ui.py [cleanup]   (run seed_iter13_ui.py first; its cleanup removes the user + UI13 notifications)
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    mdb.notifications.delete_many({"order_number": {"$regex": "^UI13"}})
    sys.exit()
u = mdb.users.find_one({"email": "delivered+ui13@resend.dev"})
mdb.users.update_one({"id": u["id"]}, {"$set": {"addresses": [
    {"name": "TEST Mottagare", "address": "Sparadgatan 5", "postal_code": "50330", "city": "Borås"},
    {"name": "", "address": "Andra vägen 9", "postal_code": "41101", "city": "Göteborg"}]}})
o = mdb.orders.find_one({"order_number": "UI13NEW"})
for a in mdb.users.find({"role": "admin"}):
    mdb.notifications.insert_one({"id": str(uuid.uuid4()), "user_id": a["id"], "kind": "new", "order_id": o["id"],
                                  "order_number": "UI13NEW", "title": "Ny order UI13NEW", "body": "TEST_UI13 Bygg · 1 st",
                                  "read": False, "created_at": datetime.now(timezone.utc).isoformat()})
print("seeded", o["id"])
