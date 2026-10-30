"""Shared database client, auth helpers and dependencies."""
import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("workwear")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ISSUER = "workwear-order-api"
TOKEN_DAYS = 30

bearer = HTTPBearer(auto_error=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user["id"], "role": user["role"], "iss": JWT_ISSUER, "iat": now,
               "exp": now + timedelta(days=TOKEN_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def city_name(city_id: Optional[str]) -> Optional[str]:
    if not city_id:
        return None
    c = await db.cities.find_one({"id": city_id}, {"_id": 0})
    return c["name"] if c else None


async def public_user(u: dict) -> dict:
    return {
        "id": u["id"], "email": u["email"], "role": u["role"], "name": u.get("name") or "", "phone": u.get("phone", ""),
        "company": u.get("company", ""), "org_number": u.get("org_number") or "",
        "city_id": u.get("city_id"), "city_name": await city_name(u.get("city_id")),
        "disabled": u.get("disabled", False), "created_at": u.get("created_at"),
        "credits_enabled": bool(u.get("credits_enabled")), "credits": int(u.get("credits") or 0),
    }


def company_key(name: str) -> str:
    """Same company regardless of case or extra spaces: 'Patriks  Bygg' == 'patriks bygg'."""
    return " ".join((name or "").split()).lower()


async def company_credits_default(company: str) -> bool:
    c = await db.companies.find_one({"key": company_key(company)}, {"_id": 0})
    return bool(c and c.get("credits_enabled"))


async def canonical_company(name: str) -> str:
    """Collapse spaces and reuse an existing company's spelling when it matches ignoring case."""
    clean = " ".join((name or "").split())
    if not clean:
        return clean

    rx = {"$regex": r"^\s*" + r"\s+".join(re.escape(w) for w in clean.split()) + r"\s*$", "$options": "i"}
    counts: dict = {}
    async for u in db.users.find({"company": rx}, {"_id": 0, "company": 1}):
        s = " ".join(u["company"].split())
        counts[s] = counts.get(s, 0) + 1
    return max(counts, key=counts.get) if counts else clean


async def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    err = HTTPException(status_code=401, detail="Ogiltig eller utgången inloggning")
    if not cred or cred.scheme.lower() != "bearer":
        raise err
    try:
        claims = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER)
    except jwt.InvalidTokenError:
        raise err
    user = await db.users.find_one({"id": claims.get("sub"), "disabled": {"$ne": True}}, {"_id": 0})
    if not user:
        raise err
    return user


async def admin_only(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Kräver admin-behörighet")
    return user


async def notify(user_id: str, order: Optional[dict], kind: str, title: str, body: str, limit: int = 300, push: bool = True):
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "user_id": user_id, "kind": kind, "order_id": order["id"] if order else None,
        "order_number": order["order_number"] if order else None, "title": title, "body": body[:limit], "read": False,
        "created_at": now_iso()})
    if push:
        from routes.push import push_safe  # local import: routes.push imports core
        asyncio.create_task(push_safe([user_id], title, body, f"/order/{order['id']}" if order else "/notifications",
                                      "offers" if kind == "broadcast" else "orders"))


def customer_city_filter(user: dict) -> dict:
    """Products an admin hid for the customer's store are invisible to that customer."""
    if user.get("role") == "admin" or not user.get("city_id"):
        return {}
    return {"hidden_city_ids": {"$ne": user["city_id"]}}
