import asyncio
import os
import uuid

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

import scraper
from core import client, db, hash_pw, logger, now_iso
from routes import admin, auth, catalog, favorites, orders
from routes.auth import LOCKOUT_MINUTES

app = FastAPI()


@app.get("/health", include_in_schema=False)
@app.head("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


api = APIRouter(prefix="/api")
for r in (auth.router, catalog.router, orders.router, admin.router, favorites.router):
    api.include_router(r)
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("part_no", unique=True)
    await db.cities.create_index("id", unique=True)
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.login_attempts.create_index("at", expireAfterSeconds=LOCKOUT_MINUTES * 60)
    await db.login_attempts.create_index("email")
    await db.password_resets.create_index("expire_at", expireAfterSeconds=0)
    await db.password_resets.create_index("email")
    await db.orders.create_index("order_number", unique=True)
    await db.favorites.create_index([("user_id", 1), ("part_no", 1), ("color_code", 1)], unique=True)
    if not await db.counters.find_one({"id": "order_number"}):
        await db.counters.insert_one({"id": "order_number", "seq": await db.orders.count_documents({})})
    seeds = [(os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"])]
    if os.environ.get("SECOND_ADMIN_EMAIL") and os.environ.get("SECOND_ADMIN_PASSWORD"):
        seeds.append((os.environ["SECOND_ADMIN_EMAIL"], os.environ["SECOND_ADMIN_PASSWORD"]))
    for raw_email, pw in seeds:
        admin_email = raw_email.strip().lower()
        # Insert only when absent; never reset an existing password on restart.
        r = await db.users.update_one(
            {"email": admin_email},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()), "email": admin_email, "password_hash": hash_pw(pw),
                "phone": "", "company": "Admin", "org_number": "", "city_id": None, "role": "admin",
                "disabled": False, "created_at": now_iso(),
            }},
            upsert=True,
        )
        if r.upserted_id is not None:
            logger.info("Seeded admin account %s", admin_email)
    if await db.cities.count_documents({}) == 0:
        for n in ["Stockholm", "Göteborg", "Malmö"]:
            await db.cities.insert_one({"id": str(uuid.uuid4()), "name": n})
    if await db.products.count_documents({}) == 0 or not (await db.settings.find_one({"id": "catalog_tree"}) or {}).get("filters"):
        asyncio.create_task(scraper.scrape_catalog(db))


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
