"""HTML for order emails and the order reply page (pure functions, no DB access)."""
from html import escape
from typing import Optional

from fastapi.responses import HTMLResponse

from emailer import EMAIL_FROM_NAME


DELIVERY_LABELS = {"store": "Hämtas i butik", "parcel_box": "Hämtas i paketbox", "ship": "Skickas"}


def delivery_text(d: Optional[dict]) -> str:
    if not d:
        return "-"
    label = DELIVERY_LABELS.get(d.get("method"), "-")
    if d.get("method") != "ship":
        return label
    parts = [d.get("name"), d.get("address"), f'{d.get("postal_code", "")} {d.get("city", "")}'.strip()]
    return label + ": " + ", ".join(x for x in parts if x)


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
