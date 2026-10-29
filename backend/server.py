import asyncio
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import scraper  # noqa: E402
from emailer import EMAIL_FROM_NAME, send_email  # noqa: E402
from emailer import _assert_safe_email as assert_safe_email  # noqa: E402
from pymongo import ReturnDocument  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ISSUER = "workwear-order-api"
TOKEN_DAYS = 30

app = FastAPI()
bearer = HTTPBearer(auto_error=False)


@app.get("/health", include_in_schema=False)
@app.head("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


api = APIRouter(prefix="/api")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- models
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


class CityIn(BaseModel):
    name: str = Field(min_length=1)


class SettingsIn(BaseModel):
    order_email: EmailStr


class UserUpdate(BaseModel):
    phone: Optional[str] = None
    company: Optional[str] = None
    org_number: Optional[str] = None
    city_id: Optional[str] = None
    disabled: Optional[bool] = None
    role: Optional[str] = None


class OrderItemIn(BaseModel):
    part_no: str
    color_code: Optional[str] = None
    size: str
    quantity: int = Field(ge=1, le=9999)


class OrderIn(BaseModel):
    items: List[OrderItemIn] = Field(min_length=1)
    comment: Optional[str] = Field(default="", max_length=2000)


# ---------------------------------------------------------------- auth helpers
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
        "id": u["id"], "email": u["email"], "role": u["role"], "phone": u.get("phone", ""),
        "company": u.get("company", ""), "org_number": u.get("org_number") or "",
        "city_id": u.get("city_id"), "city_name": await city_name(u.get("city_id")),
        "disabled": u.get("disabled", False), "created_at": u.get("created_at"),
    }


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


# ---------------------------------------------------------------- auth routes
@api.post("/auth/register")
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


@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.strip().lower()}, {"_id": 0})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "Fel e-post eller lösenord")
    if user.get("disabled"):
        raise HTTPException(403, "Kontot är spärrat. Kontakta administratören.")
    return {"access_token": make_token(user), "user": await public_user(user)}


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return await public_user(user)


# ---------------------------------------------------------------- cities (public list)
@api.get("/cities")
async def list_cities():
    return await db.cities.find({}, {"_id": 0}).sort("name", 1).to_list(500)


# ---------------------------------------------------------------- products
@api.get("/categories")
async def categories(_: dict = Depends(current_user)):
    tree = await db.settings.find_one({"id": "catalog_tree"}, {"_id": 0}) or {}
    counts = {r["_id"]: r["n"] async for r in db.products.aggregate([
        {"$match": {"active": {"$ne": False}}}, {"$unwind": "$groups"}, {"$group": {"_id": "$groups", "n": {"$sum": 1}}}])}
    sub_counts = {r["_id"]: r["n"] async for r in db.products.aggregate([
        {"$match": {"active": {"$ne": False}}}, {"$unwind": "$categories"}, {"$group": {"_id": "$categories", "n": {"$sum": 1}}}])}
    out = []
    for g in tree.get("groups", []):
        if not counts.get(g["slug"]):
            continue
        children = [{**c, "count": sub_counts[c["slug"]]} for c in g["children"] if sub_counts.get(c["slug"])]
        out.append({"slug": g["slug"], "name": g["name"], "count": counts[g["slug"]], "children": children})
    return out


@api.get("/products")
async def products(
    q: str = "", group: str = "", category: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=60),
    _: dict = Depends(current_user),
):
    flt: dict = {"active": {"$ne": False}}
    if group:
        flt["groups"] = group
    if category:
        flt["categories"] = category
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"name": rx}, {"part_no": rx}]
    total = await db.products.count_documents(flt)
    proj = {"_id": 0, "description": 0}
    items = await db.products.find(flt, proj).sort("sort_index", 1).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": items, "total": total, "page": page, "has_more": page * page_size < total,
            "syncing": scraper.status["running"]}


@api.get("/products/{part_no}")
async def product(part_no: str, _: dict = Depends(current_user)):
    p = await db.products.find_one({"part_no": part_no}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Produkten hittades inte")
    return p


# ---------------------------------------------------------------- orders
def order_email_html(order: dict, confirm_url: str) -> str:
    rows = "".join(
        f'<tr><td style="padding:8px;border-bottom:1px solid #ddd">{escape(i["part_no"])}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #ddd">{escape(i["name"])}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #ddd">{escape(i.get("color_name") or "-")}'
        f'{" (" + escape(i["color_code"]) + ")" if i.get("color_code") else ""}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #ddd">{escape(i["size"])}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">{i["quantity"]}</td></tr>'
        for i in order["items"]
    )
    c = order["customer"]
    comment = escape(order.get("comment") or "-").replace("\n", "<br>")
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;color:#111">'
        '<tr><td style="padding:24px">'
        f'<h2 style="margin:0 0 8px">Ny beställning {escape(order["order_number"])}</h2>'
        f'<p style="margin:0 0 16px">Företag: <strong>{escape(c["company"])}</strong></p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-bottom:16px">'
        f'<tr><td style="padding:2px 12px 2px 0">Organisationsnummer:</td><td>{escape(c.get("org_number") or "-")}</td></tr>'
        f'<tr><td style="padding:2px 12px 2px 0">Ort:</td><td>{escape(c.get("city_name") or "-")}</td></tr>'
        f'<tr><td style="padding:2px 12px 2px 0">Beställare:</td><td>{escape(c["email"])}</td></tr>'
        f'<tr><td style="padding:2px 12px 2px 0">Telefon:</td><td>{escape(c.get("phone") or "-")}</td></tr>'
        '</table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">'
        '<tr style="background:#FF9900"><th align="left" style="padding:8px">Artikelnummer</th>'
        '<th align="left" style="padding:8px">Produkt</th><th align="left" style="padding:8px">Färg</th>'
        '<th align="left" style="padding:8px">Storlek</th><th align="right" style="padding:8px">Antal</th></tr>'
        f'{rows}</table>'
        f'<p style="margin:16px 0 4px"><strong>Kommentar / önskat leveransdatum:</strong></p><p style="margin:0">{comment}</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px"><tr>'
        f'<td style="background:#FF9900;border-radius:6px"><a href="{escape(confirm_url)}" '
        'style="display:inline-block;padding:14px 28px;color:#000;font-weight:bold;text-decoration:none;'
        'text-transform:uppercase;letter-spacing:1px">Bekräfta order</a></td></tr></table>'
        '<p style="font-size:13px;color:#555;margin:8px 0 0">Öppnar en sida där du kan skicka ett svar till beställaren, '
        't.ex. när leverans sker.</p>'
        f'<p style="font-size:12px;color:#888;margin-top:24px">Skickat av {escape(EMAIL_FROM_NAME)}.</p>'
        '</td></tr></table>'
    )


@api.post("/orders")
async def create_order(body: OrderIn, request: Request, user: dict = Depends(current_user)):
    items = []
    for it in body.items:
        p = await db.products.find_one({"part_no": it.part_no}, {"_id": 0})
        if not p:
            raise HTTPException(400, f"Okänd artikel {it.part_no}")
        if p.get("sizes") and it.size not in p["sizes"]:
            raise HTTPException(400, f"Storlek {it.size} finns inte för {p['name']}")
        color = next((c for c in p.get("colors", []) if c["code"] == it.color_code), None)
        if it.color_code and not color:
            raise HTTPException(400, f"Färg {it.color_code} finns inte för {p['name']}")
        items.append({"part_no": p["part_no"], "name": p["name"], "size": it.size, "quantity": it.quantity,
                      "color_code": color["code"] if color else None,
                      "color_name": color["name"] if color else None,
                      "image_url": (color or {}).get("image_url") or p.get("image_url")})
    settings = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    recipient = settings.get("order_email")
    if not recipient:
        raise HTTPException(503, "Beställningar kan inte tas emot just nu – mottagaradress saknas. Kontakta administratören.")
    counter = await db.counters.find_one_and_update(
        {"id": "order_number"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    order = {
        "id": str(uuid.uuid4()), "order_number": f"B{10000 + counter['seq']}", "user_id": user["id"],
        "customer": {"email": user["email"], "company": user.get("company", ""), "phone": user.get("phone", ""),
                     "org_number": user.get("org_number", ""), "city_name": await city_name(user.get("city_id"))},
        "items": items, "comment": (body.comment or "").strip(), "created_at": now_iso(),
        "email_status": "pending", "sent_to": recipient,
        "status": "new", "confirm_token": secrets.token_urlsafe(24), "replies": [],
    }
    subject = f"Beställning {order['order_number']} – {order['customer']['company']}"
    html = order_email_html(order, f"{public_base(request)}/api/order-reply/{order['confirm_token']}")
    try:
        assert_safe_email(subject, html)
    except ValueError:
        raise HTTPException(400, "Kommentaren innehåller otillåtna ord (t.ex. om kortuppgifter eller lösenord). Ändra kommentaren och försök igen.")
    await db.orders.insert_one(dict(order))
    try:
        await send_email(to=recipient, subject=subject, html=html, reply_to=user["email"])
        order["email_status"] = "sent"
    except Exception:
        # Order is saved; tell the client so it can show a warning instead of retrying (avoids duplicates).
        order["email_status"] = "failed"
        await db.orders.update_one({"id": order["id"]}, {"$set": {"email_status": "failed"}})
        order.pop("sent_to", None)
        order.pop("confirm_token", None)
        return order
    await db.orders.update_one({"id": order["id"]}, {"$set": {"email_status": "sent"}})
    order.pop("sent_to", None)
    order.pop("confirm_token", None)
    return order


@api.get("/orders")
async def my_orders(user: dict = Depends(current_user)):
    return await db.orders.find({"user_id": user["id"]}, {"_id": 0, "sent_to": 0, "confirm_token": 0}).sort("created_at", -1).to_list(200)


# ---------------------------------------------------------------- order reply (link in order email)
MAX_REPLIES = 10


def public_base(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"https://{host}"


def reply_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html lang="sv"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(title)}</title><style>'
        'body{margin:0;background:#121212;color:#fff;font-family:Arial,Helvetica,sans-serif}'
        '.w{max-width:560px;margin:0 auto;padding:24px}.bar{width:8px;height:28px;background:#FF9900;display:inline-block;'
        'vertical-align:middle;margin-right:10px}h1{display:inline;font-size:26px;text-transform:uppercase;vertical-align:middle}'
        '.c{background:#1C1C1E;border:1px solid #333;border-radius:8px;padding:16px;margin-top:16px}'
        '.m{color:#8A8A8A;font-size:13px}.r{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #2C2C2C;gap:12px}'
        '.q{color:#FFCC00;font-weight:bold;white-space:nowrap}textarea{width:100%;box-sizing:border-box;min-height:140px;background:#2C2C2E;'
        'color:#fff;border:1px solid #333;border-radius:8px;padding:12px;font-size:16px;font-family:inherit}'
        'button{width:100%;margin-top:12px;background:#FF9900;color:#000;border:0;border-radius:8px;padding:16px;font-size:17px;'
        'font-weight:bold;text-transform:uppercase;letter-spacing:1px}.ok{border-left:4px solid #4CAF50}.err{border-left:4px solid #F44336}'
        '.rep{background:#2C2C2E;border-radius:6px;padding:10px;margin-top:8px;white-space:pre-wrap}'
        f'</style></head><body><div class="w">{body}</div></body></html>'
    )


def order_block(order: dict) -> str:
    rows = "".join(
        f'<div class="r"><div>{escape(i["name"])}<div class="m">{escape(i["part_no"])}'
        f'{"-" + escape(i["color_code"]) if i.get("color_code") else ""} · Storlek {escape(i["size"])}</div></div>'
        f'<div class="q">{i["quantity"]} st</div></div>' for i in order["items"])
    c = order["customer"]
    comment = f'<p class="m" style="margin-top:12px">Kommentar: {escape(order["comment"])}</p>' if order.get("comment") else ""
    return (f'<div class="c"><strong>{escape(c["company"])}</strong><div class="m">{escape(c["email"])} · '
            f'{escape(c.get("phone") or "")}</div>{rows}{comment}</div>')


def reply_email_html(order: dict, message: str) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #ddd">{escape(i["part_no"])}'
        f'{"-" + escape(i["color_code"]) if i.get("color_code") else ""}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #ddd">{escape(i["name"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #ddd">{escape(i["size"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #ddd;text-align:right">{i["quantity"]}</td></tr>'
        for i in order["items"])
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;color:#111"><tr><td style="padding:24px">'
        f'<h2 style="margin:0 0 8px">Din order {escape(order["order_number"])} är bekräftad</h2>'
        '<p style="margin:0 0 8px"><strong>Meddelande från leverantören:</strong></p>'
        f'<p style="margin:0 0 16px;padding:12px;background:#FFF4E0;border-left:4px solid #FF9900">'
        f'{escape(message).replace(chr(10), "<br>")}</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">'
        '<tr style="background:#FF9900"><th align="left" style="padding:6px 8px">Artikelnr</th>'
        '<th align="left" style="padding:6px 8px">Produkt</th><th align="left" style="padding:6px 8px">Storlek</th>'
        f'<th align="right" style="padding:6px 8px">Antal</th></tr>{rows}</table>'
        f'<p style="font-size:12px;color:#888;margin-top:24px">Skickat av {escape(EMAIL_FROM_NAME)}. '
        'Du ser även svaret under Ordrar i appen.</p></td></tr></table>')


async def _order_by_token(token: str) -> Optional[dict]:
    if len(token) < 20:
        return None
    return await db.orders.find_one({"confirm_token": token}, {"_id": 0})


def _reply_form(order: dict, token: str, error: str = "", message: str = "") -> HTMLResponse:
    replies = "".join(f'<div class="rep">{escape(r["message"])}<div class="m">{escape(r["created_at"][:16].replace("T", " "))} UTC</div></div>'
                      for r in order.get("replies", []))
    prev = f'<div class="c ok"><strong>Tidigare svar</strong>{replies}</div>' if replies else ""
    err = f'<div class="c err">{escape(error)}</div>' if error else ""
    return reply_page(
        f"Bekräfta order {order['order_number']}",
        f'<span class="bar"></span><h1>Bekräfta order {escape(order["order_number"])}</h1>'
        f'{order_block(order)}{prev}{err}'
        f'<form method="post" action="/api/order-reply/{escape(token)}" class="c">'
        '<label for="message"><strong>Svar till beställaren</strong></label>'
        '<p class="m">T.ex. "Leverans sker om 15 min" eller "Levereras torsdag v.24".</p>'
        f'<textarea id="message" name="message" maxlength="2000" required placeholder="Skriv ditt meddelande...">{escape(message)}</textarea>'
        '<button type="submit">Bekräfta & skicka svar</button></form>')


@api.get("/order-reply/{token}", response_class=HTMLResponse)
async def order_reply_page(token: str):
    order = await _order_by_token(token)
    if not order:
        return reply_page("Ordern hittades inte", '<div class="c err">Länken är ogiltig eller ordern finns inte längre.</div>')
    return _reply_form(order, token)


@api.post("/order-reply/{token}", response_class=HTMLResponse)
async def order_reply_submit(token: str, request: Request):
    order = await _order_by_token(token)
    if not order:
        return reply_page("Ordern hittades inte", '<div class="c err">Länken är ogiltig eller ordern finns inte längre.</div>')
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    message = (form.get("message", [""])[0]).strip()[:2000]
    if not message:
        return _reply_form(order, token, "Skriv ett meddelande innan du skickar.")
    if len(order.get("replies", [])) >= MAX_REPLIES:
        return _reply_form(order, token, "Maximalt antal svar för denna order är uppnått.", message)
    subject = f"Orderbekräftelse {order['order_number']}"
    html = reply_email_html(order, message)
    try:
        assert_safe_email(subject, html)
    except ValueError:
        return _reply_form(order, token, "Meddelandet innehåller otillåtna ord (t.ex. om kortuppgifter eller lösenord). Skriv om det.", message)
    settings = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    try:
        await send_email(to=order["customer"]["email"], subject=subject, html=html, reply_to=settings.get("order_email"))
    except HTTPException:
        return _reply_form(order, token, "Mejlet kunde inte skickas just nu. Försök igen om en stund.", message)
    reply = {"message": message, "created_at": now_iso()}
    await db.orders.update_one({"id": order["id"]}, {"$push": {"replies": reply},
                                                     "$set": {"status": "confirmed", "confirmed_at": reply["created_at"]}})
    return reply_page(
        "Svar skickat",
        f'<span class="bar"></span><h1>Svar skickat</h1><div class="c ok">Ditt svar har skickats till '
        f'<strong>{escape(order["customer"]["email"])}</strong> och ordern {escape(order["order_number"])} är markerad som bekräftad.'
        f'<div class="rep">{escape(message)}</div></div>'
        f'<p class="m" style="margin-top:16px"><a style="color:#FF9900" href="/api/order-reply/{escape(token)}">Skicka ytterligare ett svar</a></p>')


# ---------------------------------------------------------------- admin
@api.get("/admin/settings")
async def get_settings(_: dict = Depends(admin_only)):
    s = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    return {"order_email": s.get("order_email", ""), "catalog": {**scraper.status},
            "product_count": await db.products.count_documents({"active": {"$ne": False}})}


@api.put("/admin/settings")
async def put_settings(body: SettingsIn, _: dict = Depends(admin_only)):
    await db.settings.update_one({"id": "global"}, {"$set": {"order_email": body.order_email.lower()}}, upsert=True)
    return {"order_email": body.order_email.lower()}


@api.post("/admin/catalog/sync")
async def sync_catalog(_: dict = Depends(admin_only)):
    if not scraper.status["running"]:
        asyncio.create_task(scraper.scrape_catalog(db))
    return {"started": True}


@api.post("/admin/cities")
async def add_city(body: CityIn, _: dict = Depends(admin_only)):
    name = body.name.strip()
    if await db.cities.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(409, "Orten finns redan")
    city = {"id": str(uuid.uuid4()), "name": name}
    await db.cities.insert_one(dict(city))
    return city


@api.put("/admin/cities/{city_id}")
async def rename_city(city_id: str, body: CityIn, _: dict = Depends(admin_only)):
    name = body.name.strip()
    if await db.cities.find_one({"id": {"$ne": city_id}, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(409, "Orten finns redan")
    r = await db.cities.update_one({"id": city_id}, {"$set": {"name": body.name.strip()}})
    if not r.matched_count:
        raise HTTPException(404, "Orten hittades inte")
    return {"id": city_id, "name": body.name.strip()}


@api.delete("/admin/cities/{city_id}")
async def delete_city(city_id: str, _: dict = Depends(admin_only)):
    r = await db.cities.delete_one({"id": city_id})
    if not r.deleted_count:
        raise HTTPException(404, "Orten hittades inte")
    await db.users.update_many({"city_id": city_id}, {"$set": {"city_id": None}})
    return {"ok": True}


@api.get("/admin/users")
async def admin_users(q: str = "", _: dict = Depends(admin_only)):
    flt: dict = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"email": rx}, {"company": rx}]
    users = await db.users.find(flt, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(1000)
    return [await public_user(u) for u in users]


@api.get("/admin/users/{user_id}")
async def admin_user(user_id: str, _: dict = Depends(admin_only)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(404, "Kontot hittades inte")
    orders = await db.orders.count_documents({"user_id": user_id})
    return {**await public_user(u), "order_count": orders}


@api.put("/admin/users/{user_id}")
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
    r = await db.users.update_one({"id": user_id}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(404, "Kontot hittades inte")
    return await public_user(await db.users.find_one({"id": user_id}, {"_id": 0}))


@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(admin_only)):
    if user_id == admin["id"]:
        raise HTTPException(400, "Du kan inte ta bort ditt eget konto")
    await db.users.delete_one({"id": user_id})
    return {"ok": True}


@api.get("/admin/orders")
async def admin_orders(_: dict = Depends(admin_only)):
    return await db.orders.find({}, {"_id": 0, "confirm_token": 0}).sort("created_at", -1).to_list(500)


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("part_no", unique=True)
    await db.cities.create_index("id", unique=True)
    await db.orders.create_index("order_number", unique=True)
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
    if await db.products.count_documents({}) == 0 or not await db.settings.find_one({"id": "catalog_tree"}):
        asyncio.create_task(scraper.scrape_catalog(db))


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
