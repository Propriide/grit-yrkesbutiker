# Iteration 18: order_emails.py output must equal the pre-refactor routes/orders.py templates (git HEAD). Unit-level, no network.
import ast
import subprocess
import sys

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
NAMES = ["DELIVERY_LABELS", "delivery_text", "order_email_html", "reply_page", "order_block", "reply_email_html"]


def _old_namespace():
    try:
        src = subprocess.check_output(["git", "-C", "/app", "show", "HEAD:backend/routes/orders.py"], text=True)
    except Exception:
        pytest.skip("git HEAD version not available")
    tree = ast.parse(src)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in NAMES for t in n.targets))]
    if len(keep) < len(NAMES):
        pytest.skip("HEAD already refactored")
    ns = {}
    exec("from html import escape\nfrom typing import Optional\nfrom fastapi.responses import HTMLResponse\n"
         "from emailer import EMAIL_FROM_NAME\n", ns)
    exec(compile(ast.Module(body=keep, type_ignores=[]), "old", "exec"), ns)
    return ns


ORDER = {"order_number": "B1<x>", "comment": "Rad1\nRad2 <b>&", "items": [
    {"part_no": "123", "name": "Jacka <i>", "size": "C50", "quantity": 3, "color_code": "9900", "color_name": "Svart"},
    {"part_no": "456", "name": "Byxa", "size": "M", "quantity": 1, "color_code": None, "color_name": None}],
    "customer": {"company": "Bolag & Co", "email": "a@b.se", "phone": "070", "org_number": "", "city_name": "Borås"}}
DELIVERIES = [None, {"method": "store"}, {"method": "parcel_box"}, {"method": "weird"},
              {"method": "ship", "name": "N", "address": "Gata 1", "postal_code": "50330", "city": "Borås"},
              {"method": "ship", "name": "", "address": "Gata 1", "postal_code": "", "city": ""}]


@pytest.mark.parametrize("d", DELIVERIES)
def test_templates_identical(d):
    import order_emails as new
    old = _old_namespace()
    o = dict(ORDER, delivery=d)
    assert new.DELIVERY_LABELS == old["DELIVERY_LABELS"]
    assert new.delivery_text(d) == old["delivery_text"](d)
    assert new.order_email_html(o, "https://x/api/order-reply/t\"ok") == old["order_email_html"](o, "https://x/api/order-reply/t\"ok")
    assert new.order_block(o) == old["order_block"](o)
    for a in ("confirm", "decline"):
        assert new.reply_email_html(o, "Hej\n<script>", a) == old["reply_email_html"](o, "Hej\n<script>", a)
    assert new.reply_page("T<", "<b>x</b>").body == old["reply_page"]("T<", "<b>x</b>").body
