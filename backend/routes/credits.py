from fastapi import APIRouter, Depends

from core import current_user, db

router = APIRouter()


@router.get("/credits")
async def my_credits(user: dict = Depends(current_user)):
    if not user.get("credits_enabled"):
        return {"enabled": False, "balance": 0, "history": []}
    history = await db.credit_tx.find({"user_id": user["id"]}, {"_id": 0, "by": 0}).sort("created_at", -1).to_list(100)
    return {"enabled": True, "balance": int(user.get("credits") or 0), "history": history}
