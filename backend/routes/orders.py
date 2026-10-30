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
from emailer import EMAIL_FROM_NAME, send_email
from emailer import _assert_safe_email as assert_safe_email

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


DELIVERY_LABELS = {"store": "Hämtas i butik", "parcel_box": "Hämtas i paketbox", "ship": "Skickas"}


class OrderIn(BaseModel):
    items: List[OrderItemIn] = Field(min_length=1)
    comment: Optional[str] = Field(default="", max_length=2000)
    delivery: DeliveryIn


def delivery_text(d: Optional[dict]) -> str:
    if not d:
        return "-"
    label = DELIVERY_LABELS.get(d.get("method"), "-")
    if d.get("method") != "ship":
        return label
    parts = [d.get("name"), d.get("address"), f'{d.get("postal_code", "")} {d.get("city", "")}'.strip()]
    return label + ": " + ", ".join(x for x in parts if x)


CUSTOMER_ORDER_PROJ = {"_id": 0, "sent_to": 0, "confirm_token": 0, "order_value": 0}


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
        f'<tr><td style="padding:2px 12px 2px 0">Leverans:</td><td><strong>{escape(delivery_text(order.get("delivery")))}</strong></td></tr>'
        '</table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">'
        '<tr style="background:#D0102E;color:#fff"><th align="left" style="padding:8px">Artikelnummer</th>'
        '<th align="left" style="padding:8px">Produkt</th><th align="left" style="padding:8px">Färg</th>'
        '<th align="left" style="padding:8px">Storlek</th><th align="right" style="padding:8px">Antal</th></tr>'
        f'{rows}</table>'
        f'<p style="margin:16px 0 4px"><strong>Kommentar / önskat leveransdatum:</strong></p><p style="margin:0">{comment}</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px"><tr>'
        f'<td style="background:#D0102E;border-radius:6px"><a href="{escape(confirm_url)}" '
        'style="display:inline-block;padding:14px 28px;color:#fff;font-weight:bold;text-decoration:none;'
        'text-transform:uppercase;letter-spacing:1px">Bekräfta order</a></td></tr></table>'
        '<p style="font-size:13px;color:#555;margin:8px 0 0">Öppnar en sida där du kan skicka ett svar till beställaren, '
        't.ex. när leverans sker.</p>'
        f'<p style="font-size:12px;color:#888;margin-top:24px">Skickat av {escape(EMAIL_FROM_NAME)}.</p>'
        '</td></tr></table>'
    )


@router.post("/orders")
async def create_order(body: OrderIn, request: Request, user: dict = Depends(current_user)):
    d = body.delivery
    if d.method not in DELIVERY_LABELS:
        raise HTTPException(400, "Välj leveranssätt")
    delivery = {"method": d.method}
    if d.method == "ship":
        delivery.update(name=d.name.strip(), address=d.address.strip(), postal_code=d.postal_code.strip(), city=d.city.strip())
        if not (delivery["address"] and delivery["postal_code"] and delivery["city"]):
            raise HTTPException(400, "Fyll i adress, postnummer och ort för leveransen")
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


@router.get("/notifications")
async def notifications(user: dict = Depends(current_user)):
    items = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"items": items, "unread": unread}


@router.post("/notifications/read-all")
async def notifications_read_all(user: dict = Depends(current_user)):
    await db.notifications.update_many({"user_id": user["id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/notifications/{notif_id}/read")
async def notification_read(notif_id: str, user: dict = Depends(current_user)):
    await db.notifications.update_one({"id": notif_id, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"ok": True}


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


def reply_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html lang="sv"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(title)}</title><style>'
        'body{margin:0;background:#121212;color:#fff;font-family:Arial,Helvetica,sans-serif}'
        '.w{max-width:560px;margin:0 auto;padding:24px}.bar{width:8px;height:28px;background:#D0102E;display:inline-block;'
        'vertical-align:middle;margin-right:10px}h1{display:inline;font-size:26px;text-transform:uppercase;vertical-align:middle}'
        '.c{background:#1C1C1E;border:1px solid #333;border-radius:8px;padding:16px;margin-top:16px}'
        '.m{color:#8A8A8A;font-size:13px}.r{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #2C2C2C;gap:12px}'
        '.q{color:#FF4D5E;font-weight:bold;white-space:nowrap}textarea{width:100%;box-sizing:border-box;min-height:140px;background:#2C2C2E;'
        'color:#fff;border:1px solid #333;border-radius:8px;padding:12px;font-size:16px;font-family:inherit}'
        'button{width:100%;margin-top:12px;background:#D0102E;color:#fff;border:0;border-radius:8px;padding:16px;font-size:17px;'
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
    if order.get("delivery"):
        comment += f'<p class="m">Leverans: <strong style="color:#fff">{escape(delivery_text(order["delivery"]))}</strong></p>'
    return (f'<div class="c"><strong>{escape(c["company"])}</strong><div class="m">{escape(c["email"])} · '
            f'{escape(c.get("phone") or "")}</div>{rows}{comment}</div>')


def reply_email_html(order: dict, message: str, action: str = "confirm") -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #ddd">{escape(i["part_no"])}'
        f'{"-" + escape(i["color_code"]) if i.get("color_code") else ""}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #ddd">{escape(i["name"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #ddd">{escape(i["size"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #ddd;text-align:right">{i["quantity"]}</td></tr>'
        for i in order["items"])
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;color:#111"><tr><td style="padding:24px">'
        f'<h2 style="margin:0 0 8px">Din order {escape(order["order_number"])} '
        f'{"är bekräftad" if action == "confirm" else "har nekats"}</h2>'
        '<p style="margin:0 0 8px"><strong>Meddelande från leverantören:</strong></p>'
        f'<p style="margin:0 0 16px;padding:12px;background:#FDECEE;border-left:4px solid #D0102E">'
        f'{escape(message).replace(chr(10), "<br>")}</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">'
        '<tr style="background:#D0102E;color:#fff"><th align="left" style="padding:6px 8px">Artikelnr</th>'
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
    message: str = Field(min_length=1, max_length=2000)
    action: str = "confirm"


@router.post("/admin/orders/{order_id}/reply")
async def admin_reply_order(order_id: str, body: ReplyIn, _: dict = Depends(admin_only)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Ordern hittades inte")
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "Skriv ett meddelande innan du skickar.")
    if body.action not in ("confirm", "decline"):
        raise HTTPException(400, "Ogiltig åtgärd")
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
    if not message:
        return _reply_form(order, token, "Skriv ett meddelande innan du skickar.")
    action = "decline" if form.get("action", [""])[0] == "decline" else "confirm"
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
