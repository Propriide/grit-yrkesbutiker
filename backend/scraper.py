"""Scrapes the Blåkläder Swedish product catalog (Next.js __NEXT_DATA__ payload)."""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE = "https://www.blaklader.se"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WorkwearOrderApp/1.0)"}

# (slug, display name) — the categories pulled into the app
CATEGORIES = [
    ("jackor", "Jackor"),
    ("byxor", "Byxor"),
    ("hangselbyxor", "Hängselbyxor"),
    ("trojor", "Tröjor"),
    ("tshirts-langarmad-tshirt", "T-shirts"),
    ("skjortor", "Skjortor"),
    ("vastar", "Västar"),
    ("shorts-piratbyxor", "Shorts"),
    ("overaller", "Overaller"),
    ("skyddsskor", "Skyddsskor"),
    ("handskar", "Handskar"),
    ("kepsar-mossor", "Kepsar & mössor"),
]
MAX_PAGES_PER_CATEGORY = 4
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

status = {"running": False, "last_run": None, "count": 0, "error": None}


def _next_data(html: str) -> dict:
    m = NEXT_RE.search(html)
    if not m:
        raise ValueError("No __NEXT_DATA__ found")
    return json.loads(m.group(1))


def _strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _parse_list_item(item: dict, category: str) -> dict:
    inner = item["innerProduct"]
    variant_images = {}
    for v in inner.get("variants") or []:
        if v.get("imageUrl") and v.get("colorCodeId") not in variant_images:
            variant_images[v["colorCodeId"]] = v["imageUrl"]
    colors = []
    for c in item.get("colors") or []:
        colors.append({
            "code": c.get("code"),
            "name": c.get("value"),
            "image_url": variant_images.get(c.get("id")) or inner.get("imageUrl"),
        })
    return {
        "part_no": inner["partNo"],
        "name": inner.get("name") or inner["partNo"],
        "slug": inner.get("uniqueName"),
        "description": _strip_html(inner.get("description", "")),
        "price": inner.get("price"),
        "image_url": inner.get("imageUrl"),
        "colors": colors,
        "category": category,
        "sizes": [],
    }


async def _fetch(client: httpx.AsyncClient, path: str) -> str:
    r = await client.get(BASE + path)
    r.raise_for_status()
    return r.text


async def _fetch_sizes(client: httpx.AsyncClient, sem: asyncio.Semaphore, product: dict):
    async with sem:
        try:
            data = _next_data(await _fetch(client, f"/sv/produkt/{product['slug']}"))
            params = data["props"]["pageProps"]["productResults"].get("parametrics") or {}
            values = (params.get("Size") or params.get("SizeAlternate") or {}).get("values") or []
            values.sort(key=lambda v: v.get("sortOrder", 0))
            product["sizes"] = [v["value"] for v in values if v.get("value")]
        except Exception as e:  # keep the product, just without sizes
            logger.warning("Size fetch failed for %s: %s", product["part_no"], e)


async def scrape_catalog(db) -> int:
    if status["running"]:
        return 0
    status.update(running=True, error=None)
    products: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for slug, label in CATEGORIES:
                for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
                    try:
                        data = _next_data(await _fetch(client, f"/sv/alla-produkter/{slug}?page={page}"))
                        plm = data["props"]["pageProps"]["plm"]
                    except Exception as e:
                        logger.warning("Listing fetch failed %s p%s: %s", slug, page, e)
                        break
                    items = plm.get("productsList") or []
                    for it in items:
                        try:
                            p = _parse_list_item(it, label)
                            products.setdefault(p["part_no"], p)
                        except Exception as e:
                            logger.warning("Parse failed: %s", e)
                    if not items or page * (plm.get("pageSize") or 15) >= (plm.get("total") or 0):
                        break
            sem = asyncio.Semaphore(6)
            await asyncio.gather(*[_fetch_sizes(client, sem, p) for p in products.values() if p.get("slug")])

        now = datetime.now(timezone.utc).isoformat()
        for i, p in enumerate(products.values()):
            p["sort_index"] = i
            p["updated_at"] = now
            if not p["sizes"]:
                p["sizes"] = ["One size"]
            await db.products.update_one({"part_no": p["part_no"]}, {"$set": p}, upsert=True)
        status.update(count=len(products), last_run=now)
        logger.info("Catalog scrape complete: %d products", len(products))
        return len(products)
    except Exception as e:
        status["error"] = str(e)
        logger.exception("Catalog scrape failed")
        return 0
    finally:
        status["running"] = False
