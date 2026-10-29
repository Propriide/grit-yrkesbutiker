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

ROOT_CATEGORY_ID = 11945  # "Alla produkter" on blaklader.se
# Top-level groups in the same order as the Blåkläder menu
GROUP_ORDER = ["overdelar", "underdelar", "understall", "underklader", "vattentata-plagg", "handskar", "arbetsskor", "tillbehor"]
PAGE_SIZE = 15
# Filters shown in the app, same order as the Blåkläder filter panel. "Size" maps to product sizes.
FILTER_CODES = [
    "FilterFunction", "FilterCollections", "FilterTypeOfGarment", "Size", "Color", "FilterCertification",
    "FilterHighvisClassification", "FilterHighVisCoCertification", "FilterMaterial", "P6412",
    "FilterFlameResistantCollection", "FilterMiljomarkning",
]
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


def _parse_list_item(item: dict, color_names: dict[int, str]) -> dict:
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
            "base": sorted({color_names[i] for i in c.get("color") or [] if i in color_names}),
        })
    return {
        "part_no": inner["partNo"],
        "name": inner.get("name") or inner["partNo"],
        "slug": inner.get("uniqueName"),
        "description": _strip_html(inner.get("description", "")),
        "image_url": inner.get("imageUrl"),
        "colors": colors,
        "gender": [v["value"] for v in ((item.get("innerParametrics") or {}).get("GenderSection") or {}).get("values") or [] if v.get("value")],
        "filters": {
            code: [v["value"] for v in ((item.get("innerParametrics") or {}).get(code) or {}).get("values") or [] if v.get("value")]
            for code in FILTER_CODES if code != "Size"
            and ((item.get("innerParametrics") or {}).get(code) or {}).get("values")
        },
        "category_ids": list(inner.get("categories") or []),
        "sizes": [],
    }


def _build_tree(nav: dict) -> tuple[list[dict], dict[int, tuple[str, str | None]]]:
    """Returns (groups, id_map). id_map: category id -> (group_slug, sub_slug|None)."""
    nodes: dict[int, dict] = {}
    for key in ("clothingCategory", "accessoriesCategory"):
        for c in nav.get(key) or []:
            if c.get("id") and c.get("slug"):
                nodes[c["id"]] = {"id": c["id"], "name": c["name"], "slug": c["slug"], "parent": c.get("parentId")}
    groups, id_map = [], {}
    for g in sorted((n for n in nodes.values() if n["parent"] == ROOT_CATEGORY_ID),
                    key=lambda n: GROUP_ORDER.index(n["slug"]) if n["slug"] in GROUP_ORDER else 99):
        children = sorted((n for n in nodes.values() if n["parent"] == g["id"]), key=lambda n: n["name"])
        groups.append({"slug": g["slug"], "name": g["name"],
                       "children": [{"slug": ch["slug"], "name": ch["name"]} for ch in children]})
        id_map[g["id"]] = (g["slug"], None)
        for ch in children:
            id_map[ch["id"]] = (g["slug"], ch["slug"])
    return groups, id_map


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
            home = _next_data(await _fetch(client, "/sv"))
            groups, id_map = _build_tree(home["props"]["stores"]["generalStore"]["navigation"])
            if not groups:
                raise ValueError("Kunde inte läsa kategoriträdet från blaklader.se")

            first = _next_data(await _fetch(client, "/sv/alla-produkter?page=1"))["props"]["pageProps"]["plm"]
            pages = {1: first.get("productsList") or []}
            filter_defs = []
            color_names: dict[int, str] = {}
            for fp in (first.get("filters") or {}).get("parametrics") or []:
                if fp.get("parametricCode") == "Color":
                    color_names = {v["id"]: v["value"] for v in fp.get("multipleValues") or [] if v.get("id")}
            for fp in (first.get("filters") or {}).get("parametrics") or []:
                if fp.get("parametricCode") in FILTER_CODES:
                    vals = sorted(fp.get("multipleValues") or [], key=lambda v: v.get("sortOrder", 0))
                    filter_defs.append({"code": fp["parametricCode"], "name": fp["name"],
                                        "values": [v["value"] for v in vals if v.get("value")]})
            filter_defs.sort(key=lambda f: FILTER_CODES.index(f["code"]))
            total_pages = -(-(first.get("total") or 0) // (first.get("pageSize") or PAGE_SIZE))
            sem = asyncio.Semaphore(6)

            async def fetch_page(n: int):
                async with sem:
                    try:
                        plm = _next_data(await _fetch(client, f"/sv/alla-produkter?page={n}"))["props"]["pageProps"]["plm"]
                        pages[n] = plm.get("productsList") or []
                    except Exception as e:
                        logger.warning("Listing page %s failed: %s", n, e)

            await asyncio.gather(*[fetch_page(n) for n in range(2, total_pages + 1)])
            for n in sorted(pages):
                for it in pages[n]:
                    try:
                        p = _parse_list_item(it, color_names)
                        if not p["filters"].get("Color"):
                            base = sorted({color_names[cid] for c in it.get("colors") or [] for cid in c.get("color") or [] if cid in color_names})
                            if base:
                                p["filters"]["Color"] = base
                        products.setdefault(p["part_no"], p)
                    except Exception as e:
                        logger.warning("Parse failed: %s", e)
            await asyncio.gather(*[_fetch_sizes(client, sem, p) for p in products.values() if p.get("slug")])

        now = datetime.now(timezone.utc).isoformat()
        for i, p in enumerate(products.values()):
            grp, subs = set(), set()
            for cid in p.pop("category_ids"):
                if cid in id_map:
                    g, s = id_map[cid]
                    grp.add(g)
                    if s:
                        subs.add(s)
            p.update(groups=sorted(grp), categories=sorted(subs), sort_index=i, updated_at=now, active=True)
            if not p["sizes"]:
                p["sizes"] = ["One size"]
            await db.products.update_one({"part_no": p["part_no"]}, {"$set": p, "$unset": {"category": "", "price": ""}}, upsert=True)
        if products:
            # Products no longer on blaklader.se are hidden, not deleted (old orders keep references).
            await db.products.update_many({"updated_at": {"$ne": now}}, {"$set": {"active": False}})
        await db.settings.update_one({"id": "catalog_tree"}, {"$set": {"groups": groups, "filters": filter_defs}}, upsert=True)
        status.update(count=len(products), last_run=now)
        logger.info("Catalog scrape complete: %d products", len(products))
        return len(products)
    except Exception as e:
        status["error"] = str(e)
        logger.exception("Catalog scrape failed")
        return 0
    finally:
        status["running"] = False
