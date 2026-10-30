import os
import re
import secrets
import uuid
from html import escape
from typing import List, Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core import admin_only, city_name, current_user, customer_city_filter, db, logger, notify, now_iso
from emailer import send_email
from emailer import _assert_safe_email as assert_safe_email
from order_emails import DELIVERY_LABELS, order_email_html, reply_email_html, reply_page, order_block

router = APIRouter()


class OrderItemIn(BaseModel):
    part_no: str
    color_code: Optional[str] = None
    size: str
    quantity: int = Field(ge=1, le=9999)


class DeliveryIn(BaseModel):
    method: str  # store | parcel_box | ship
    name: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=200)
    postal_code: str = Field(default="", max_length=20)
    city: str = Field(default="", max_length=100)


class OrderIn(BaseModel):
    items: List[OrderItemIn] = Field(min_length=1)
    comment: Optional[str] = Field(default="", max_length=2000)
    delivery: DeliveryIn


CUSTOMER_ORDER_PROJ = {"_id": 0, "sent_to": 0, "confirm_token": 0, "order_value": 0}


# ---------------------------------------------------------------- orders
@router.post("/orders")
async def create_order(body: OrderIn, request: Request, user: dict = Depends(current_user)):
    d = body.delivery
    if d.method not in DELIVERY_LABELS:
        raise HTTPException(400, "Välj leveranssätt")
    delivery = {"method": d.method}
    if d.method == "ship":
        delivery.update(name=d.name.strip(), address=d.address.strip(), postal_code=d.postal_code.strip(), city=d.city.strip())
        if not (delivery["name"] and delivery["address"] and delivery["postal_code"] and delivery["city"]):
            raise HTTPException(400, "Fyll i mottagare, adress, postnummer och ort för leveransen")
    items = []
    value = 0.0
    for it in body.items:
        p = await db.products.find_one({"part_no": it.part_no, **customer_city_filter(user)}, {"_id": 0})
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
        value += float(p.get("price") or 0) * it.quantity
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
        "items": items, "comment": (body.comment or "").strip(), "delivery": delivery, "order_value": round(value, 2),
        "created_at": now_iso(),
        "email_status": "pending", "sent_to": recipient,
        "status": "new", "confirm_token": secrets.token_urlsafe(24), "replies": [],
    }
    subject = f"Beställning {order['order_number']} – {order['customer']['company']}"
    confirm_base = public_base(request)
    logger.info("Order confirm link base: %s", confirm_base)
    html = order_email_html(order, f"{confirm_base}/api/order-reply/{order['confirm_token']}")
    try:
        assert_safe_email(subject, html)
    except ValueError:
        raise HTTPException(400, "Kommentaren innehåller otillåtna ord (t.ex. om kortuppgifter eller lösenord). Ändra kommentaren och försök igen.")
    await db.orders.insert_one(dict(order))
    if delivery["method"] == "ship":
        addr = {k: delivery[k] for k in ("name", "address", "postal_code", "city")}
        saved = [a for a in user.get("addresses") or [] if {k: a.get(k) for k in addr} != addr]
        await db.users.update_one({"id": user["id"]}, {"$set": {"addresses": [addr, *saved][:10]}})
    try:
        await send_email(to=recipient, subject=subject, html=html, reply_to=user["email"])
        order["email_status"] = "sent"
    except Exception:
        order["email_status"] = "failed"
    await db.orders.update_one({"id": order["id"]}, {"$set": {"email_status": order["email_status"]}})
    try:
        async for a in db.users.find({"role": "admin", "disabled": {"$ne": True}}, {"_id": 0, "id": 1}):
            note = "" if order["email_status"] == "sent" else " (mejlet kunde inte skickas)"
            await notify(a["id"], order, "new", f"Ny order {order['order_number']}{note}",
                         f"{order['customer']['company']} · {sum(i['quantity'] for i in items)} st")
    except Exception:
        logger.exception("Admin notification failed for order %s", order["order_number"])
    for k in ("sent_to", "confirm_token", "order_value"):
        order.pop(k, None)
    return order


@router.get("/addresses")
async def my_addresses(user: dict = Depends(current_user)):
    """Delivery addresses the user shipped to before, newest first."""
    return user.get("addresses") or []


class AddressIn(BaseModel):
    name: str = ""
    address: str = ""
    postal_code: str = ""
    city: str = ""


@router.post("/addresses/remove")
async def remove_address(body: AddressIn, user: dict = Depends(current_user)):
    target = body.model_dump()
    await db.users.update_one({"id": user["id"]}, {"$pull": {"addresses": target}})
    return (await db.users.find_one({"id": user["id"]}, {"_id": 0, "addresses": 1})).get("addresses") or []


@router.get("/orders")
async def my_orders(user: dict = Depends(current_user)):
    return await db.orders.find({"user_id": user["id"]}, CUSTOMER_ORDER_PROJ).sort("created_at", -1).to_list(200)


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: dict = Depends(current_user)):
    flt = {"id": order_id} if user["role"] == "admin" else {"id": order_id, "user_id": user["id"]}
    o = await db.orders.find_one(flt, {"_id": 0, "sent_to": 0, "confirm_token": 0} if user["role"] == "admin" else CUSTOMER_ORDER_PROJ)
    if not o:
        raise HTTPException(404, "Ordern hittades inte")
    return o


# ---------------------------------------------------------------- order reply (link in order email)
MAX_REPLIES = 10


_HOST_RX = re.compile(r"^[a-z0-9.-]+(:\d+)?$")
PUBLIC_HOST_SUFFIXES = tuple(s.strip() for s in os.environ["PUBLIC_HOST_SUFFIXES"].split(",") if s.strip())


def public_base(request: Request) -> str:
    # Only trust a forwarded host that belongs to our own allowlisted domains.
    for h in (request.headers.get("x-forwarded-host"), request.headers.get("host")):
        host = (h or "").split(",")[0].strip().lower()
        if _HOST_RX.match(host) and host.split(":")[0].endswith(PUBLIC_HOST_SUFFIXES):
            return f"https://{host}"
    raise HTTPException(400, "Ogiltig värd")


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
        f'<textarea id="message" name="message" maxlength="2000" placeholder="Valfritt vid bekräftelse – krävs vid nekande">{escape(message)}</textarea>'
        '<div style="display:flex;gap:8px"><button type="submit" name="action" value="confirm" style="flex:2">Bekräfta & skicka</button>'
        '<button type="submit" name="action" value="decline" style="flex:1;background:#2C2C2E;color:#F44336;border:1px solid #F44336">Neka</button></div></form>')


@router.get("/order-reply/{token}", response_class=HTMLResponse)
async def order_reply_page(token: str):
    order = await _order_by_token(token)
    if not order:
        return reply_page("Ordern hittades inte", '<div class="c err">Länken är ogiltig eller ordern finns inte längre.</div>')
    return _reply_form(order, token)


async def send_order_reply(order: dict, message: str, action: str = "confirm") -> Optional[str]:
    """Confirms/declines the order and emails the message to the orderer. Returns an error text or None on success."""
    if len(order.get("replies", [])) >= MAX_REPLIES:
        return "Maximalt antal svar för denna order är uppnått."
    subject = f"{'Orderbekräftelse' if action == 'confirm' else 'Order nekad'} {order['order_number']}"
    html = reply_email_html(order, message, action)
    try:
        assert_safe_email(subject, html)
    except ValueError:
        return "Meddelandet innehåller otillåtna ord (t.ex. om kortuppgifter eller lösenord). Skriv om det."
    settings = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    try:
        await send_email(to=order["customer"]["email"], subject=subject, html=html, reply_to=settings.get("order_email"))
    except HTTPException as e:
        return e.detail if e.status_code == 503 else "Mejlet kunde inte skickas just nu. Försök igen om en stund."
    reply = {"message": message, "created_at": now_iso(), "action": action}
    status = "confirmed" if action == "confirm" else "declined"
    upd = {"status": status, f"{status}_at": reply["created_at"]}
    if order.get("status") == "ready" and action == "confirm":
        upd = {}  # an extra message on a finished order must not move it back from "Klar"
    await db.orders.update_one({"id": order["id"]}, {"$push": {"replies": reply}, **({"$set": upd} if upd else {})})
    await notify(order["user_id"], order, status,
                 f"Order {order['order_number']} {'bekräftad' if action == 'confirm' else 'nekad'}", message)
    if action == "confirm":
        await award_credits(order)
    return None


async def award_credits(order: dict):
    """1 credit per 100 kr (excl. VAT) of the order value, once per order, if credits are on for the customer."""
    u = await db.users.find_one({"id": order["user_id"]}, {"_id": 0, "credits_enabled": 1})
    amount = int((order.get("order_value") or 0) // 100)
    if not u or not u.get("credits_enabled") or amount <= 0:
        return
    claimed = await db.orders.update_one({"id": order["id"], "credits_earned": {"$exists": False}}, {"$set": {"credits_earned": amount}})
    if not claimed.modified_count:
        return
    await db.users.update_one({"id": order["user_id"]}, {"$inc": {"credits": amount}})
    await db.credit_tx.insert_one({"id": str(uuid.uuid4()), "user_id": order["user_id"], "amount": amount, "reason": "order",
                                   "order_id": order["id"], "order_number": order["order_number"], "note": "", "created_at": now_iso()})


class ReplyIn(BaseModel):
    message: str = Field(default="", max_length=2000)
    action: str = "confirm"


DEFAULT_CONFIRM_MESSAGE = "Din order är bekräftad."


@router.post("/admin/orders/{order_id}/reply")
async def admin_reply_order(order_id: str, body: ReplyIn, _: dict = Depends(admin_only)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Ordern hittades inte")
    if body.action not in ("confirm", "decline"):
        raise HTTPException(400, "Ogiltig åtgärd")
    message = body.message.strip() or (DEFAULT_CONFIRM_MESSAGE if body.action == "confirm" else "")
    if not message:
        raise HTTPException(400, "Skriv varför ordern nekas.")
    err = await send_order_reply(order, message, body.action)
    if err:
        raise HTTPException(400, err)
    return await db.orders.find_one({"id": order_id}, {"_id": 0, "confirm_token": 0})


@router.post("/order-reply/{token}", response_class=HTMLResponse)
async def order_reply_submit(token: str, request: Request):
    order = await _order_by_token(token)
    if not order:
        return reply_page("Ordern hittades inte", '<div class="c err">Länken är ogiltig eller ordern finns inte längre.</div>')
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    message = (form.get("message", [""])[0]).strip()[:2000]
    action = "decline" if form.get("action", [""])[0] == "decline" else "confirm"
    if not message and action == "confirm":
        message = DEFAULT_CONFIRM_MESSAGE
    if not message:
        return _reply_form(order, token, "Skriv varför ordern nekas.")
    err = await send_order_reply(order, message, action)
    if err:
        return _reply_form(order, token, err, message)
    state = "bekräftad" if action == "confirm" else "nekad"
    return reply_page(
        "Svar skickat",
        f'<span class="bar"></span><h1>Svar skickat</h1><div class="c ok">Ditt svar har skickats till '
        f'<strong>{escape(order["customer"]["email"])}</strong> och ordern {escape(order["order_number"])} är markerad som {state}.'
        f'<div class="rep">{escape(message)}</div></div>'
        f'<p class="m" style="margin-top:16px"><a style="color:#D0102E" href="/api/order-reply/{escape(token)}">Skicka ytterligare ett svar</a></p>')


@router.post("/admin/orders/{order_id}/ready")
async def admin_mark_ready(order_id: str, _: dict = Depends(admin_only)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Ordern hittades inte")
    if order.get("status") != "confirmed":
        raise HTTPException(400, "Bara bekräftade ordrar kan klarmarkeras")
    ready_at = now_iso()
    r = await db.orders.update_one({"id": order_id, "status": "confirmed"}, {"$set": {"status": "ready", "ready_at": ready_at}})
    if not r.modified_count:
        raise HTTPException(400, "Bara bekräftade ordrar kan klarmarkeras")
    try:
        await notify(order["user_id"], order, "ready", f"Order {order['order_number']} är klar", "Ordern är klar.")
    except Exception:
        logger.exception("Ready notification failed for order %s", order["order_number"])
    return await db.orders.find_one({"id": order_id}, {"_id": 0, "confirm_token": 0})


@router.get("/admin/orders")
async def admin_orders(_: dict = Depends(admin_only)):
    return await db.orders.find({}, {"_id": 0, "confirm_token": 0}).sort("created_at", -1).to_list(500)
