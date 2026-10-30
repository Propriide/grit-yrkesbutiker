"""Emergent managed push relay (SuprSend). Device tokens are never stored here; recipients are user ids."""
import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import current_user

logger = logging.getLogger("workwear.push")

PUSH_BASE_URL = "https://integrations.emergentagent.com"
PUSH_KEY = os.environ.get("EMERGENT_PUSH_KEY", "placeholder")

_client = httpx.AsyncClient(base_url=PUSH_BASE_URL, headers={"X-Push-Key": PUSH_KEY}, timeout=10.0)

router = APIRouter()


class RegisterPushBody(BaseModel):
    user_id: str = ""
    platform: str  # "android" | "ios"
    device_token: str


@router.post("/register-push", status_code=201)
async def register_push(body: RegisterPushBody, user: dict = Depends(current_user)):
    # The token is always tied to the logged-in user, whatever user_id the client sent.
    payload = {"user_id": user["id"], "platform": body.platform, "device_token": body.device_token}
    resp = await _client.post("/api/v1/push/users/register", json=payload)
    if resp.status_code == 401:
        raise HTTPException(500, "EMERGENT_PUSH_KEY missing or invalid")
    if resp.status_code >= 500:
        raise HTTPException(502, "Push provider unavailable")
    resp.raise_for_status()
    return {"status": "registered"}


async def send_push(recipients: list[str], data: dict, idempotency_key: str | None = None, _attempt: int = 0) -> None:
    if not recipients:
        return
    if len(recipients) > 100:
        raise ValueError("max 100 recipients per /trigger call; chunk before sending")
    if "title" not in data or "message" not in data:
        raise ValueError("data must include title and message")
    payload: dict = {"recipients": recipients, "data": data}
    if idempotency_key:
        payload["$idempotency_key"] = idempotency_key
    resp = await _client.post("/api/v1/push/trigger", json=payload)
    if resp.status_code == 401:
        raise HTTPException(500, "EMERGENT_PUSH_KEY missing or invalid")
    code = resp.json().get("code", "") if resp.headers.get("content-type", "").startswith("application/json") else ""
    if code == "idempotency_key_in_progress" and idempotency_key and _attempt < 3:
        await asyncio.sleep(3)
        return await send_push(recipients, data, idempotency_key=idempotency_key, _attempt=_attempt + 1)
    if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
        logger.warning(f"Push paused: {code} ({resp.status_code}): {resp.json().get('message', '')}")
        return
    if resp.status_code >= 500:
        raise HTTPException(502, "Push provider unavailable")
    resp.raise_for_status()


async def push_safe(recipients: list[str], title: str, message: str, action_url: str | None = None, category: str = "orders"):
    """Fire-and-forget: native push (apps) + web push (installed PWA). Respects the users' notification choices
    and never blocks the order/notification flow."""
    from routes.webpush import allowed_recipients, send_webpush
    try:
        recipients = await allowed_recipients(recipients, category)
    except Exception as e:
        logger.warning(f"Pref lookup failed: {e}")
    data = {"title": title, "message": message[:500]}
    if action_url:
        data["action_url"] = action_url
    for i in range(0, len(recipients), 100):
        try:
            await send_push(recipients[i:i + 100], data)
        except Exception as e:
            logger.warning(f"Push failed (non-blocking): {e}")
    try:
        await send_webpush(recipients, title, message, action_url or "/")
    except Exception as e:
        logger.warning(f"Web push failed (non-blocking): {e}")
