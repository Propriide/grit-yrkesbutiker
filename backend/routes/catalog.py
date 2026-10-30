import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import scraper
from core import admin_only, current_user, customer_city_filter, db

router = APIRouter()


# ---------------------------------------------------------------- cities (public list)
@router.get("/cities")
async def list_cities():
    return await db.cities.find({}, {"_id": 0}).sort("name", 1).to_list(500)


# ---------------------------------------------------------------- store start page
class StoreIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=4000)
    address: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    hours: str = Field(default="", max_length=600)


DEFAULT_STORE = {
    "title": "Välkommen till YP Yrkesbutiker",
    "text": "Här beställer du arbetskläder från Blåkläders sortiment till ditt företag. Välj plagg, storlek och antal – vi återkommer med bekräftelse och leveranstid.",
    "address": "", "phone": "", "email": "", "hours": "",
}


async def store_for(store_id: str) -> dict:
    s = await db.stores.find_one({"id": store_id}, {"_id": 0}) or {}
    return {**DEFAULT_STORE, **{k: v for k, v in s.items() if k in DEFAULT_STORE}}


@router.get("/home")
async def home(user: dict = Depends(current_user)):
    city = await db.cities.find_one({"id": user.get("city_id")}, {"_id": 0}) if user.get("city_id") else None
    custom = city and await db.stores.find_one({"id": city["id"]})
    data = await store_for(city["id"] if custom else "default")
    return {**data, "city_name": city["name"] if city else None}


@router.get("/admin/stores/{store_id}")
async def admin_get_store(store_id: str, _: dict = Depends(admin_only)):
    if store_id != "default" and not await db.cities.find_one({"id": store_id}):
        raise HTTPException(404, "Orten hittades inte")
    has_custom = bool(await db.stores.find_one({"id": store_id}))
    return {**await store_for(store_id if has_custom else "default"), "id": store_id, "custom": has_custom}


@router.put("/admin/stores/{store_id}")
async def admin_put_store(store_id: str, body: StoreIn, _: dict = Depends(admin_only)):
    if store_id != "default" and not await db.cities.find_one({"id": store_id}):
        raise HTTPException(404, "Orten hittades inte")
    data = {k: v.strip() for k, v in body.model_dump().items()}
    if not data["title"] or not data["text"]:
        raise HTTPException(400, "Rubrik och information får inte vara tomma")
    await db.stores.update_one({"id": store_id}, {"$set": {**data, "id": store_id}}, upsert=True)
    return {**data, "id": store_id, "custom": True}


@router.delete("/admin/stores/{store_id}")
async def admin_reset_store(store_id: str, _: dict = Depends(admin_only)):
    """Reset a city's start page to the default text (removes only that city's override)."""
    if store_id == "default":
        raise HTTPException(400, "Standardsidan kan inte återställas")
    if not await db.cities.find_one({"id": store_id}):
        raise HTTPException(404, "Orten hittades inte")
    await db.stores.delete_one({"id": store_id})
    return {**await store_for("default"), "id": store_id, "custom": False}


# ---------------------------------------------------------------- products
@router.get("/categories")
async def categories(gender: str = "", user: dict = Depends(current_user)):
    tree = await db.settings.find_one({"id": "catalog_tree"}, {"_id": 0}) or {}
    match = _base_filter("", "", "", "", gender, user)
    counts = {r["_id"]: r["n"] async for r in db.products.aggregate([
        {"$match": match}, {"$unwind": "$groups"}, {"$group": {"_id": "$groups", "n": {"$sum": 1}}}])}
    sub_counts = {r["_id"]: r["n"] async for r in db.products.aggregate([
        {"$match": match}, {"$unwind": "$categories"}, {"$group": {"_id": "$categories", "n": {"$sum": 1}}}])}
    out = []
    for g in tree.get("groups", []):
        if not counts.get(g["slug"]):
            continue
        children = [{**c, "count": sub_counts[c["slug"]]} for c in g["children"] if sub_counts.get(c["slug"])]
        out.append({"slug": g["slug"], "name": g["name"], "count": counts[g["slug"]], "children": children})
    return out


GENDERS = {"herr": ["Herr", "Unisex"], "dam": ["Dam", "Unisex"]}


def _gender_clause(gender: str) -> Optional[dict]:
    """Herr/Dam view like blaklader.se: gendered garments of that gender + unisex + ungendered items (gloves, shoes...)."""
    vals = GENDERS.get(gender)
    if not vals:
        return None
    return {"$or": [{"gender": {"$in": vals}}, {"gender.0": {"$exists": False}}]}


def _base_filter(q: str, group: str, category: str, filters: str, gender: str = "", user: Optional[dict] = None) -> dict:
    flt: dict = {"active": {"$ne": False}, **customer_city_filter(user or {})}
    if (g := _gender_clause(gender)):
        flt["$and"] = [g]
    if group:
        flt["groups"] = group
    if category:
        flt["categories"] = category
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"name": rx}, {"part_no": rx}]
    if filters:
        try:
            sel = json.loads(filters)
        except ValueError:
            raise HTTPException(400, "Ogiltigt filter")
        if not isinstance(sel, dict):
            raise HTTPException(400, "Ogiltigt filter")
        for code, values in sel.items():
            if code not in scraper.FILTER_CODES or not isinstance(values, list) or not values:
                continue
            vals = [str(v) for v in values][:50]
            flt["sizes" if code == "Size" else f"filters.{code}"] = {"$in": vals}
    return flt


_LETTER_SIZES = ["XXS", "XS", "S", "S/M", "M", "L", "L/XL", "XL", "XXL", "XXL/3XL"]
_NXL_RX = re.compile(r"^(\d)XL(.*)$")


def _size_key(s: str):
    if s in _LETTER_SIZES:
        return (0, _LETTER_SIZES.index(s), "", 0, s)
    m = _NXL_RX.match(s)
    if m:  # 3XL, 4XL, 4XLS, 4XLT, 7XL ... after XXL
        return (0, len(_LETTER_SIZES) + int(m.group(1)), m.group(2), 0, s)
    if s.lower() == "one size":
        return (0, 99, "", 0, s)
    m = re.match(r"^([A-Za-z]*)\s*(\d+)", s)
    if m:
        return (1, 0, m.group(1).upper(), int(m.group(2)), s)
    return (2, 0, "", 0, s)


@router.get("/filters")
async def filter_options(q: str = "", group: str = "", category: str = "", gender: str = "", user: dict = Depends(current_user)):
    """Filter panel definitions (Blåkläder order) with counts for the current group/category/search."""
    tree = await db.settings.find_one({"id": "catalog_tree"}, {"_id": 0}) or {}
    base = _base_filter(q, group, category, "", gender, user)
    out = []
    for f in tree.get("filters", []):
        field = "$sizes" if f["code"] == "Size" else f"$filters.{f['code']}"
        counts = {r["_id"]: r["n"] async for r in db.products.aggregate([
            {"$match": base}, {"$unwind": field}, {"$group": {"_id": field, "n": {"$sum": 1}}}])}
        order = f["values"] or sorted(counts)
        if f["code"] == "Size":
            order = sorted(counts, key=_size_key)
        values = [{"value": v, "count": counts[v]} for v in order if counts.get(v)]
        if values:
            out.append({"code": f["code"], "name": f["name"], "values": values})
    return out


@router.get("/products")
async def products(
    q: str = "", group: str = "", category: str = "", filters: str = "", gender: str = "", hidden_in: str = "",
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=60),
    user: dict = Depends(current_user),
):
    flt = _base_filter(q, group, category, filters, gender, user)
    if hidden_in and user.get("role") == "admin":
        # Admin view: only products hidden somewhere ("any") or in one specific store.
        flt["hidden_city_ids"] = {"$exists": True, "$ne": []} if hidden_in == "any" else hidden_in
    total = await db.products.count_documents(flt)
    proj = {"_id": 0, "description": 0, "price": 0, "filters": 0}
    if user.get("role") != "admin":
        proj["hidden_city_ids"] = 0
    sel_colors = _selected_colors(filters)
    bought, bought_color = await _purchase_history(user["id"], sel_colors)
    color_score: object = 0
    if sel_colors:
        # Rank like a shop would: pure solid colour (only selected bases), solid with extra tone, only-selected combos, mixed.
        c_base = {"$ifNull": ["$$c.base", []]}
        c_hit = {"$gt": [{"$size": {"$setIntersection": [c_base, sel_colors]}}, 0]}
        c_solid = {"$not": [{"$regexMatch": {"input": "$$c.name", "regex": "/"}}]}
        c_only = {"$and": [c_hit, {"$setIsSubset": [c_base, sel_colors]}]}
        color_score = {"$max": {"$map": {"input": {"$ifNull": ["$colors", []]}, "as": "c", "in": {"$switch": {"branches": [
            {"case": {"$and": [c_solid, c_only]}, "then": 3},
            {"case": {"$and": [c_solid, c_hit]}, "then": 2},
            {"case": c_only, "then": 1},
        ], "default": 0}}}}}
    # The customer's own purchases come first, most recently bought first (respecting the active filters).
    idx = {"$indexOfArray": [bought, "$part_no"]}
    bought_rank = {"$cond": [{"$gte": [idx, 0]}, idx, 1_000_000]}
    items = await db.products.aggregate([
        {"$match": flt}, {"$addFields": {"_bought": bought_rank, "_score": color_score}},
        {"$sort": {"_bought": 1, "_score": -1, "sort_index": 1}},
        {"$skip": (page - 1) * page_size}, {"$limit": page_size}, {"$project": {**proj, "_score": 0, "_bought": 0}},
    ]).to_list(page_size)
    for p in items:
        if p["part_no"] in bought_color:
            p["purchased"] = True
            p["purchased_color"] = bought_color[p["part_no"]]
    return {"items": items, "total": total, "page": page, "has_more": page * page_size < total,
            "syncing": scraper.status["running"]}


async def _purchase_history(user_id: str, sel_colors: list[str]) -> tuple[list[str], dict]:
    """Part numbers the user ordered (newest first) and the colour last bought. With a colour filter only
    purchases in a matching colour count, so a black filter puts the customer's black trousers first."""
    lines = []
    async for o in db.orders.find({"user_id": user_id, "status": {"$ne": "declined"}}, {"_id": 0, "items": 1, "created_at": 1}).sort("created_at", -1).limit(300):
        lines += [(i["part_no"], i.get("color_code")) for i in o["items"]]
    if not lines:
        return [], {}
    bases: dict = {}
    if sel_colors:
        async for p in db.products.find({"part_no": {"$in": list({pn for pn, _ in lines})}}, {"_id": 0, "part_no": 1, "colors": 1}):
            for c in p.get("colors") or []:
                bases[(p["part_no"], c["code"])] = set(c.get("base") or [])
    order: list[str] = []
    color: dict = {}
    for pn, cc in lines:
        if pn in color:
            continue
        if sel_colors and not (bases.get((pn, cc), set()) & set(sel_colors)):
            continue
        color[pn] = cc
        order.append(pn)
    return order, color


def _selected_colors(filters: str) -> list[str]:
    try:
        sel = json.loads(filters) if filters else {}
        return [str(v) for v in sel.get("Color", [])][:20] if isinstance(sel, dict) else []
    except ValueError:
        return []


@router.get("/products/{part_no}")
async def product(part_no: str, user: dict = Depends(current_user)):
    proj = {"_id": 0, "price": 0} if user.get("role") == "admin" else {"_id": 0, "price": 0, "hidden_city_ids": 0}
    p = await db.products.find_one({"part_no": part_no, **customer_city_filter(user)}, proj)
    if not p:
        raise HTTPException(404, "Produkten hittades inte")
    return p
