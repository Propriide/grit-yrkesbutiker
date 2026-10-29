import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import current_user, db, hash_pw, logger, make_token, now_iso, public_user, verify_pw
from emailer import EMAIL_FROM_NAME, send_email

router = APIRouter()


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    phone: str = Field(min_length=5)
    company: str = Field(min_length=1)
    org_number: Optional[str] = None
    city_id: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/register")
async def register(body: RegisterIn):
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "E-postadressen är redan registrerad")
    if body.city_id and not await db.cities.find_one({"id": body.city_id}):
        raise HTTPException(400, "Ogiltig ort")
    if not body.city_id and await db.cities.count_documents({}) > 0:
        raise HTTPException(400, "Välj ort")
    user = {
        "id": str(uuid.uuid4()), "email": email, "password_hash": hash_pw(body.password),
        "phone": body.phone.strip(), "company": body.company.strip(),
        "org_number": (body.org_number or "").strip(), "city_id": body.city_id,
        "role": "customer", "disabled": False, "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    return {"access_token": make_token(user), "user": await public_user(user)}


MAX_FAILED_LOGINS = 5  # per email + IP
MAX_FAILED_LOGINS_PER_EMAIL = 30  # across all IPs (slows distributed guessing)
LOCKOUT_MINUTES = 15


@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[-1].strip()
    since = (datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
    per_ip = await db.login_attempts.count_documents({"email": email, "ip": ip, "at_iso": {"$gte": since}})
    per_email = await db.login_attempts.count_documents({"email": email, "at_iso": {"$gte": since}})
    if per_ip >= MAX_FAILED_LOGINS or per_email >= MAX_FAILED_LOGINS_PER_EMAIL:
        raise HTTPException(429, f"För många misslyckade inloggningar. Försök igen om {LOCKOUT_MINUTES} minuter.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_pw(body.password, user["password_hash"]):
        await db.login_attempts.insert_one({"email": email, "ip": ip, "at": datetime.now(timezone.utc), "at_iso": now_iso()})
        raise HTTPException(401, "Fel e-post eller lösenord")
    await db.login_attempts.delete_many({"email": email, "ip": ip})
    if user.get("disabled"):
        raise HTTPException(403, "Kontot är spärrat. Kontakta administratören.")
    return {"access_token": make_token(user), "user": await public_user(user)}


@router.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return await public_user(user)


class ProfileUpdate(BaseModel):
    phone: str = Field(min_length=5, max_length=40)
    company: str = Field(min_length=1, max_length=200)
    org_number: Optional[str] = Field(default="", max_length=40)
    city_id: Optional[str] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=72)


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=72)


RESET_MINUTES = 15
MAX_RESET_REQUESTS = 3
MAX_RESET_ATTEMPTS = 5


@router.put("/auth/me")
async def update_me(body: ProfileUpdate, user: dict = Depends(current_user)):
    if body.city_id and not await db.cities.find_one({"id": body.city_id}):
        raise HTTPException(400, "Ogiltig ort")
    upd = {"phone": body.phone.strip(), "company": body.company.strip(),
           "org_number": (body.org_number or "").strip(), "city_id": body.city_id or None}
    await db.users.update_one({"id": user["id"]}, {"$set": upd})
    return await public_user({**user, **upd})


@router.post("/auth/change-password")
async def change_password(body: ChangePasswordIn, user: dict = Depends(current_user)):
    if not verify_pw(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Nuvarande lösenord är fel")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_pw(body.new_password)}})
    return {"ok": True}


@router.post("/auth/forgot-password")
async def forgot_password(body: ForgotIn):
    """Always returns the same neutral response so emails cannot be enumerated."""
    neutral = {"ok": True, "message": "Om adressen finns hos oss har en kod skickats."}
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email, "disabled": {"$ne": True}}, {"_id": 0})
    if not user:
        return neutral
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=RESET_MINUTES)).isoformat()
    if await db.password_resets.count_documents({"email": email, "created_at": {"$gte": since}}) >= MAX_RESET_REQUESTS:
        return neutral
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.password_resets.insert_one({
        "email": email, "code_hash": hash_pw(code), "attempts": 0, "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=RESET_MINUTES)).isoformat(), "expire_at": now + timedelta(minutes=RESET_MINUTES)})
    html = (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;color:#111"><tr><td style="padding:24px">'
        '<h2 style="margin:0 0 12px">Återställ ditt lösenord</h2>'
        '<p style="margin:0 0 12px">Ange koden nedan i appen för att välja ett nytt lösenord. Koden gäller i '
        f'{RESET_MINUTES} minuter.</p>'
        f'<p style="font-size:32px;font-weight:bold;letter-spacing:6px;margin:0 0 16px">{code}</p>'
        '<p style="font-size:13px;color:#555">Har du inte bett om detta kan du ignorera mejlet. Dela aldrig koden med någon.</p>'
        f'<p style="font-size:12px;color:#888;margin-top:24px">Skickat av {escape(EMAIL_FROM_NAME)}.</p>'
        '</td></tr></table>')
    async def _send():
        try:
            await send_email(to=email, subject="Din återställningskod", html=html)
        except HTTPException:
            logger.warning("Password reset email could not be sent")

    asyncio.create_task(_send())  # background: same response time for known/unknown emails
    return neutral


@router.post("/auth/reset-password")
async def reset_password(body: ResetIn):
    email = body.email.strip().lower()
    err = HTTPException(400, "Koden är fel eller har gått ut. Begär en ny kod.")
    rec = await db.password_resets.find_one({"email": email, "expires_at": {"$gte": now_iso()}}, sort=[("created_at", -1)])
    if not rec or rec.get("attempts", 0) >= MAX_RESET_ATTEMPTS:
        raise err
    if not verify_pw(body.code.strip(), rec["code_hash"]):
        await db.password_resets.update_one({"_id": rec["_id"]}, {"$inc": {"attempts": 1}})
        raise err
    await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pw(body.new_password)}})
    await db.password_resets.delete_many({"email": email})
    await db.login_attempts.delete_many({"email": email})
    return {"ok": True}
