"""Web Push (VAPID) for the installed PWA on iPhone (iOS 16.4+) and Android, plus per-user notification preferences."""
import asyncio
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pywebpush import WebPushException, webpush

from core import current_user, db, now_iso

logger = logging.getLogger("workwear.webpush")
router = APIRouter()

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")

DEFAULT_PREFS = {"orders": True, "offers": True}


class SubKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: SubKeys


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(max_length=1000)


class PrefsIn(BaseModel):
    orders: bool = True
    offers: bool = True


@router.get("/webpush/public-key")
async def public_key():
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/webpush/subscribe", status_code=201)
async def subscribe(body: SubscriptionIn, user: dict = Depends(current_user)):
    if not body.endpoint.startswith("https://"):
        raise HTTPException(400, "Ogiltig prenumeration")
    await db.webpush_subs.update_one(
        {"endpoint": body.endpoint},
        {"$set": {"endpoint": body.endpoint, "keys": body.keys.model_dump(), "user_id": user["id"], "updated_at": now_iso()}},
        upsert=True)
    return {"status": "subscribed"}


@router.post("/webpush/unsubscribe")
async def unsubscribe(body: UnsubscribeIn, user: dict = Depends(current_user)):
    await db.webpush_subs.delete_one({"endpoint": body.endpoint, "user_id": user["id"]})
    return {"status": "unsubscribed"}


@router.get("/notification-prefs")
async def get_prefs(user: dict = Depends(current_user)):
    return {**DEFAULT_PREFS, **(user.get("notify_prefs") or {})}


@router.put("/notification-prefs")
async def set_prefs(body: PrefsIn, user: dict = Depends(current_user)):
    prefs = body.model_dump()
    await db.users.update_one({"id": user["id"]}, {"$set": {"notify_prefs": prefs}})
    return prefs


async def allowed_recipients(user_ids: list[str], category: str) -> list[str]:
    """Drop users who switched this notification category off."""
    off = {u["id"] async for u in db.users.find({"id": {"$in": user_ids}, f"notify_prefs.{category}": False}, {"_id": 0, "id": 1})}
    return [u for u in user_ids if u not in off]


def _send_one(sub: dict, payload: str) -> int:
    try:
        webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims={"sub": VAPID_SUBJECT}, ttl=86400)
        return 201
    except WebPushException as e:
        return e.response.status_code if e.response is not None else 0


async def send_webpush(user_ids: list[str], title: str, message: str, url: str):
    if not VAPID_PRIVATE_KEY or not user_ids:
        return
    payload = json.dumps({"title": title, "body": message[:500], "url": url})
    async for sub in db.webpush_subs.find({"user_id": {"$in": user_ids}}, {"_id": 0}):
        code = await asyncio.to_thread(_send_one, sub, payload)
        if code in (404, 410):  # subscription expired / app removed
            await db.webpush_subs.delete_one({"endpoint": sub["endpoint"]})
        elif code not in (200, 201):
            logger.warning(f"Web push failed ({code}) for {sub['endpoint'][:60]}")
