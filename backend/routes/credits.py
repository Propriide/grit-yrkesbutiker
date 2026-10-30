from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core import current_user, customer_city_filter, db

router = APIRouter()


class EstimateItem(BaseModel):
    part_no: str
    quantity: int = Field(ge=1, le=999)


class EstimateIn(BaseModel):
    items: list[EstimateItem] = Field(default_factory=list, max_length=200)


@router.get("/credits")
async def my_credits(user: dict = Depends(current_user)):
    if not user.get("credits_enabled"):
        return {"enabled": False, "balance": 0, "history": []}
    history = await db.credit_tx.find({"user_id": user["id"]}, {"_id": 0, "by": 0}).sort("created_at", -1).to_list(100)
    return {"enabled": True, "balance": int(user.get("credits") or 0), "history": history}


@router.post("/credits/estimate")
async def estimate_credits(body: EstimateIn, user: dict = Depends(current_user)):
    """Credits the cart would earn (1 per 100 kr excl. VAT). Only the credit total is returned, never prices."""
    if not user.get("credits_enabled") or not body.items:
        return {"enabled": bool(user.get("credits_enabled")), "credits": 0}
    prices = {p["part_no"]: float(p.get("price") or 0) async for p in db.products.find(
        {"part_no": {"$in": [i.part_no for i in body.items]}, **customer_city_filter(user)}, {"_id": 0, "part_no": 1, "price": 1})}
    value = sum(prices.get(i.part_no, 0) * i.quantity for i in body.items)
    return {"enabled": True, "credits": int(value // 100)}
