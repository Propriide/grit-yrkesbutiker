import asyncio
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

import scraper
from core import admin_only, canonical_company, company_credits_default, company_key, db, hash_pw, notify, now_iso, public_user

router = APIRouter()


class CityIn(BaseModel):
    name: str = Field(min_length=1)


class SettingsIn(BaseModel):
    order_email: EmailStr


class UserUpdate(BaseModel):
    phone: Optional[str] = None
    company: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=120)
    org_number: Optional[str] = None
    city_id: Optional[str] = None
    disabled: Optional[bool] = None
    role: Optional[str] = None
    credits_enabled: Optional[bool] = None


class CreditAdjustIn(BaseModel):
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(default="", max_length=300)


class CompanyCreditsIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool


class BroadcastIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    city_id: Optional[str] = None


class VisibilityIn(BaseModel):
    hidden_city_ids: list[str] = Field(default_factory=list, max_length=500)


class AdminPasswordIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=72)


@router.put("/admin/users/{user_id}/password")
async def admin_set_password(user_id: str, body: AdminPasswordIn, _: dict = Depends(admin_only)):
    r = await db.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_pw(body.new_password)}})
    if not r.matched_count:
        raise HTTPException(404, "Kontot hittades inte")
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
    await db.login_attempts.delete_many({"email": u["email"]})
    return {"ok": True}


# ---------------------------------------------------------------- admin
@router.get("/admin/settings")
async def get_settings(_: dict = Depends(admin_only)):
    s = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    return {"order_email": s.get("order_email", ""), "catalog": {**scraper.status},
            "product_count": await db.products.count_documents({"active": {"$ne": False}})}


@router.put("/admin/settings")
async def put_settings(body: SettingsIn, _: dict = Depends(admin_only)):
    await db.settings.update_one({"id": "global"}, {"$set": {"order_email": body.order_email.lower()}}, upsert=True)
    return {"order_email": body.order_email.lower()}


@router.post("/admin/catalog/sync")
async def sync_catalog(_: dict = Depends(admin_only)):
    if not scraper.status["running"]:
        asyncio.create_task(scraper.scrape_catalog(db))
    return {"started": True}


@router.post("/admin/cities")
async def add_city(body: CityIn, _: dict = Depends(admin_only)):
    name = body.name.strip()
    if await db.cities.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(409, "Orten finns redan")
    city = {"id": str(uuid.uuid4()), "name": name}
    await db.cities.insert_one(dict(city))
    return city


@router.put("/admin/cities/{city_id}")
async def rename_city(city_id: str, body: CityIn, _: dict = Depends(admin_only)):
    name = body.name.strip()
    if await db.cities.find_one({"id": {"$ne": city_id}, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(409, "Orten finns redan")
    r = await db.cities.update_one({"id": city_id}, {"$set": {"name": body.name.strip()}})
    if not r.matched_count:
        raise HTTPException(404, "Orten hittades inte")
    return {"id": city_id, "name": body.name.strip()}


@router.delete("/admin/cities/{city_id}")
async def delete_city(city_id: str, _: dict = Depends(admin_only)):
    r = await db.cities.delete_one({"id": city_id})
    if not r.deleted_count:
        raise HTTPException(404, "Orten hittades inte")
    await db.users.update_many({"city_id": city_id}, {"$set": {"city_id": None}})
    return {"ok": True}


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    phone: str = Field(default="", max_length=40)
    name: str = Field(default="", max_length=120)
    company: str = Field(min_length=1, max_length=200)
    org_number: Optional[str] = ""
    city_id: Optional[str] = None
    role: str = "customer"


@router.post("/admin/users")
async def admin_create_user(body: AdminUserCreate, _: dict = Depends(admin_only)):
    email = body.email.strip().lower()
    if body.role not in ("customer", "admin"):
        raise HTTPException(400, "Ogiltig roll")
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "E-postadressen är redan registrerad")
    if body.city_id and not await db.cities.find_one({"id": body.city_id}):
        raise HTTPException(400, "Ogiltig ort")
    user = {
        "id": str(uuid.uuid4()), "email": email, "password_hash": hash_pw(body.password),
        "name": body.name.strip(), "phone": body.phone.strip(), "company": await canonical_company(body.company), "org_number": (body.org_number or "").strip(),
        "city_id": body.city_id or None, "role": body.role, "disabled": False, "created_at": now_iso(),
    }
    user["credits_enabled"] = await company_credits_default(user["company"])
    await db.users.insert_one(dict(user))
    return await public_user(user)


@router.get("/admin/users")
async def admin_users(q: str = "", _: dict = Depends(admin_only)):
    flt: dict = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"email": rx}, {"company": rx}, {"name": rx}]
    users = await db.users.find(flt, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(1000)
    return [await public_user(u) for u in users]


@router.get("/admin/users/{user_id}")
async def admin_user(user_id: str, _: dict = Depends(admin_only)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(404, "Kontot hittades inte")
    orders = await db.orders.count_documents({"user_id": user_id})
    return {**await public_user(u), "order_count": orders}


@router.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, body: UserUpdate, admin: dict = Depends(admin_only)):
    upd = body.model_dump(exclude_none=True)
    if "role" in upd and upd["role"] not in ("customer", "admin"):
        raise HTTPException(400, "Ogiltig roll")
    if user_id == admin["id"] and (upd.get("disabled") or upd.get("role") == "customer"):
        raise HTTPException(400, "Du kan inte spärra eller degradera ditt eget konto")
    if upd.get("city_id") and not await db.cities.find_one({"id": upd["city_id"]}):
        raise HTTPException(400, "Ogiltig ort")
    if upd.get("city_id") == "":
        upd["city_id"] = None
    if "name" in upd:
        upd["name"] = upd["name"].strip()
    if "company" in upd:
        upd["company"] = await canonical_company(upd["company"])
        if not upd["company"]:
            raise HTTPException(400, "Företag är obligatoriskt")
    r = await db.users.update_one({"id": user_id}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(404, "Kontot hittades inte")
    return await public_user(await db.users.find_one({"id": user_id}, {"_id": 0}))


@router.post("/admin/users/{user_id}/credits")
async def admin_adjust_credits(user_id: str, body: CreditAdjustIn, admin: dict = Depends(admin_only)):
    if body.amount == 0:
        raise HTTPException(400, "Ange ett antal credits")
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "credits": 1})
    if not u:
        raise HTTPException(404, "Kontot hittades inte")
    if body.amount < 0:
        r = await db.users.update_one({"id": user_id, "credits": {"$gte": -body.amount}}, {"$inc": {"credits": body.amount}})
        if not r.modified_count:
            raise HTTPException(400, f"Kunden har bara {u.get('credits') or 0} credits")
    else:
        await db.users.update_one({"id": user_id}, {"$inc": {"credits": body.amount}})
    await db.credit_tx.insert_one({"id": str(uuid.uuid4()), "user_id": user_id, "amount": body.amount,
                                   "reason": "admin", "note": body.note.strip(), "by": admin["email"], "created_at": now_iso()})
    return await public_user(await db.users.find_one({"id": user_id}, {"_id": 0}))


@router.get("/admin/users/{user_id}/credits")
async def admin_credit_history(user_id: str, _: dict = Depends(admin_only)):
    return await db.credit_tx.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("/admin/companies/credits")
async def admin_company_credits(body: CompanyCreditsIn, _: dict = Depends(admin_only)):
    key = company_key(body.name)
    await db.companies.update_one({"key": key}, {"$set": {"key": key, "credits_enabled": body.enabled}}, upsert=True)
    r = await db.users.update_many({"company": _company_rx(body.name)}, {"$set": {"credits_enabled": body.enabled}})
    return {"key": key, "credits_enabled": body.enabled, "updated": r.modified_count}


@router.post("/admin/broadcast")
async def admin_broadcast(body: BroadcastIn, admin: dict = Depends(admin_only)):
    title, text = body.title.strip(), body.body.strip()
    if not title or not text:
        raise HTTPException(400, "Rubrik och meddelande får inte vara tomma")
    flt: dict = {"disabled": {"$ne": True}, "role": {"$ne": "admin"}}
    if body.city_id:
        if not await db.cities.find_one({"id": body.city_id}):
            raise HTTPException(400, "Ogiltig ort")
        flt["city_id"] = body.city_id
    ids = [u["id"] async for u in db.users.find(flt, {"_id": 0, "id": 1})]
    for uid in ids:
        await notify(uid, None, "broadcast", title, text, limit=2000)
    rec = {"id": str(uuid.uuid4()), "title": title, "body": text, "city_id": body.city_id or None,
           "recipients": len(ids), "by": admin["email"], "created_at": now_iso()}
    await db.broadcasts.insert_one(dict(rec))
    return rec


@router.get("/admin/broadcasts")
async def admin_broadcasts(_: dict = Depends(admin_only)):
    return await db.broadcasts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.put("/admin/products/{part_no}/visibility")
async def admin_product_visibility(part_no: str, body: VisibilityIn, _: dict = Depends(admin_only)):
    ids = sorted(set(body.hidden_city_ids))
    if ids and await db.cities.count_documents({"id": {"$in": ids}}) != len(ids):
        raise HTTPException(400, "Ogiltig ort")
    r = await db.products.update_one({"part_no": part_no}, {"$set": {"hidden_city_ids": ids}})
    if not r.matched_count:
        raise HTTPException(404, "Produkten hittades inte")
    return {"part_no": part_no, "hidden_city_ids": ids}


@router.get("/admin/companies")
async def admin_companies(_: dict = Depends(admin_only)):
    groups: dict = {}
    async for u in db.users.find({}, {"_id": 0, "company": 1}):
        name = " ".join((u.get("company") or "").split())
        if not name:
            continue
        g = groups.setdefault(company_key(name), {"key": company_key(name), "spellings": {}, "count": 0})
        g["count"] += 1
        g["spellings"][name] = g["spellings"].get(name, 0) + 1
    enabled = {c["key"]: c.get("credits_enabled", False) async for c in db.companies.find({}, {"_id": 0})}
    out = [{"key": g["key"], "name": max(g["spellings"], key=g["spellings"].get), "count": g["count"],
            "spellings": sorted(g["spellings"]), "credits_enabled": enabled.get(g["key"], False)} for g in groups.values()]
    return sorted(out, key=lambda c: c["name"].lower())


def _company_rx(name: str) -> dict:
    words = name.split()
    if not words:
        raise HTTPException(400, "Ange företagsnamn")
    return {"$regex": r"^\s*" + r"\s+".join(re.escape(w) for w in words) + r"\s*$", "$options": "i"}


@router.get("/admin/company-users")
async def admin_company_users(name: str, _: dict = Depends(admin_only)):
    users = await db.users.find({"company": _company_rx(name)}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(1000)
    return [await public_user(u) for u in users]


@router.get("/admin/company-orders")
async def admin_company_orders(name: str, _: dict = Depends(admin_only)):
    rx = _company_rx(name)
    ids = [u["id"] async for u in db.users.find({"company": rx}, {"_id": 0, "id": 1})]
    flt = {"$or": [{"user_id": {"$in": ids}}, {"customer.company": rx}]}
    return await db.orders.find(flt, {"_id": 0, "confirm_token": 0}).sort("created_at", -1).to_list(500)


@router.get("/admin/users/{user_id}/orders")
async def admin_user_orders(user_id: str, _: dict = Depends(admin_only)):
    return await db.orders.find({"user_id": user_id}, {"_id": 0, "confirm_token": 0}).sort("created_at", -1).to_list(500)


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(admin_only)):
    if user_id == admin["id"]:
        raise HTTPException(400, "Du kan inte ta bort ditt eget konto")
    await db.users.delete_one({"id": user_id})
    return {"ok": True}
