import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import current_user, db, now_iso

router = APIRouter()


class FavoriteIn(BaseModel):
    part_no: str
    color_code: Optional[str] = None


@router.get("/favorites")
async def list_favorites(user: dict = Depends(current_user)):
    return await db.favorites.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/favorites")
async def add_favorite(body: FavoriteIn, user: dict = Depends(current_user)):
    p = await db.products.find_one({"part_no": body.part_no}, {"_id": 0, "part_no": 1, "name": 1, "colors": 1, "image_url": 1})
    if not p:
        raise HTTPException(404, "Produkten hittades inte")
    color = next((c for c in p.get("colors", []) if c["code"] == body.color_code), None)
    if body.color_code and not color:
        raise HTTPException(400, "Färgen finns inte för produkten")
    key = {"user_id": user["id"], "part_no": p["part_no"], "color_code": color["code"] if color else None}
    existing = await db.favorites.find_one(key, {"_id": 0, "user_id": 0})
    if existing:
        return existing
    fav = {**key, "id": str(uuid.uuid4()), "name": p["name"], "color_name": color["name"] if color else None,
           "image_url": (color or {}).get("image_url") or p.get("image_url"), "created_at": now_iso()}
    await db.favorites.insert_one(dict(fav))
    fav.pop("user_id")
    return fav


@router.delete("/favorites/{fav_id}")
async def remove_favorite(fav_id: str, user: dict = Depends(current_user)):
    await db.favorites.delete_one({"id": fav_id, "user_id": user["id"]})
    return {"ok": True}
