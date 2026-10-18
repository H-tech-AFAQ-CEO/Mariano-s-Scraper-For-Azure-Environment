"""HTML -> records. Pure functions (no browser) so they are unit-testable offline.
Selector lists come from config/selectors.yaml; structural fallbacks (the /p/<slug>/<UPC> product URL,
regex price scan) keep extraction working when a class name changes."""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup

from . import deals
from .schema import finalize, fmt_price, is_approx_weight

PPM_RE = re.compile(
    r"\$\s*\d+(?:\.\d+)?\s*/\s*(?:fl\.?\s*oz|oz|lb|ct|count|ea|each|qt|gal|pt|ml|l|g|kg|sq\.?\s*ft|yd|ft|sheet|pk|pack|load|use)\b",
    re.I,
)
SIZE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:fl\.?\s*oz|oz|lb|ct|count|gal|qt|pt|ml|l|g|kg|pk|pack|sq\.?\s*ft)\b", re.I)
PRICE_RE = re.compile(r"\$\s*\d[\d,]*(?:\.\d{1,2})?")
UPC_URL_RE = re.compile(r"/p/[^/?#]+/(\d{8,14})")


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el is not None else ""


def _select(root, sels):
    for s in sels or []:
        try:
            r = root.select(s)
        except Exception:
            continue
        if r:
            return r
    return []


def first(root, sels, need_text=True):
    for s in sels or []:
        try:
            nodes = root.select(s)
        except Exception:
            continue
        for n in nodes:
            if not need_text or txt(n):
                return n
    return None


@dataclass
class Listing:
    cards: list = field(default_factory=list)       # raw card dicts
    raw_card_count: int = 0
    declared_total: int = None
    has_next: bool = False
    empty_marker: bool = False
    banner: str = ""
    logo: str = ""
    notes: list = field(default_factory=list)


def _outermost(els):
    ids = {id(e) for e in els}
    return [e for e in els if not any(id(p) in ids for p in e.parents)]


def parse_banner(soup, sel):
    b = first(soup, sel.get("store_banner"))
    logo = first(soup, sel.get("store_logo"), need_text=False)
    src = ""
    if logo is not None:
        src = logo.get("src") or logo.get("data-src") or ""
    return txt(b), src


def _abs(base, u):
    return urljoin(base, u) if u else ""


def _card_dict(card, sel, base):
    link = first(card, sel.get("card_link"), need_text=False)
    href = _abs(base, link.get("href")) if link is not None else ""
    title_el = first(card, sel.get("title"))
    title = txt(title_el)
    img = ""
    for im in card.select("img"):
        for attr in ("data-src", "src"):
            v = im.get(attr) or ""
            if v.startswith("http") or v.startswith("//"):
                img = _abs(base, v)
                break
        if img:
            break
    m = UPC_URL_RE.search(href)
    upc = m.group(1) if m else (card.get("data-upc") or card.get("data-sku") or "")
    size = txt(first(card, sel.get("size")))
    if not size:
        sm = SIZE_RE.search(title)
        size = sm.group(0) if sm else ""
    price_cur_el = first(card, sel.get("price_current"))
    price_org_el = first(card, sel.get("price_original"))
    price_cur = txt(price_cur_el)
    if not PRICE_RE.search(price_cur):
        # structural fallback: first $ amount in the card that is not struck through
        struck = {id(x) for x in _select(card, sel.get("price_original"))}
        price_cur = ""
        for node in card.find_all(string=PRICE_RE):
            if any(id(p) in struck for p in node.parents):
                continue
            price_cur = node.strip()
            break
    ppm_el = first(card, sel.get("ppm"))
    ppm = ""
    if ppm_el is not None:
        m = PPM_RE.search(txt(ppm_el))
        ppm = m.group(0) if m else ""
    if not ppm:
        m = PPM_RE.search(txt(card))
        ppm = m.group(0) if m else ""
    promos = []
    for s in sel.get("promo_digital") or []:
        try:
            promos += [(txt(n), "digital") for n in card.select(s) if txt(n)]
        except Exception:
            pass
    for n in _select(card, sel.get("promo")):
        promos.append(txt(n))
    for node in card.find_all(string=True):  # leaf-text fallback: any text that reads like a deal
        t = node.strip()
        if t and len(t) < 160 and deals.is_deal_text(t):
            promos.append(t)
    brand = txt(first(card, sel.get("brand")))
    return {
        "title": title, "url": href, "image_url": img, "upc": upc, "size": size,
        "price_cur": price_cur, "price_org": txt(price_org_el), "ppm": ppm, "promos": promos, "brand": brand,
    }


def _href_no_query(u):
    s = urlsplit(u)
    return urlunsplit((s.scheme, s.netloc, s.path, "", ""))


def parse_listing(html, sel, base_url, settings=None, coupons=False) -> Listing:
    settings = settings or {}
    soup = BeautifulSoup(html, "lxml")
    res = Listing()
    res.banner, res.logo = parse_banner(soup, sel)
    if coupons:
        cards = _outermost(_select(soup, sel.get("coupon_card")))
        res.raw_card_count = len(cards)
        for c in cards:
            res.cards.append({
                "title": txt(first(c, sel.get("title")) or c.find(["h2", "h3", "h4"])) or txt(c)[:120],
                "url": _abs(base_url, (c.find("a", href=True) or {}).get("href", "")) if c.find("a", href=True) else "",
                "image_url": _abs(base_url, (c.find("img") or {}).get("src", "")) if c.find("img") else "",
                "upc": "", "size": "", "price_cur": "", "price_org": "", "ppm": "",
                "promos": [(txt(c), "digital")], "brand": "", "coupon": True,
            })
    else:
        chosen = []
        for s in sel.get("card") or []:
            try:
                els = [e for e in soup.select(s) if first(e, sel.get("card_link"), need_text=False) is not None]
            except Exception:
                continue
            if els:
                chosen = _outermost(els)
                break
        if not chosen:  # structural fallback: group by product links
            seen = {}
            for a in soup.select('main a[href*="/p/"], a[href*="/p/"]'):
                parent = a
                for _ in range(6):
                    if parent.parent is None or parent.parent.name in ("body", "main", "html"):
                        break
                    parent = parent.parent
                    if len(parent.select('a[href*="/p/"]')) > 1:
                        parent = parent.find(lambda t: t is not None and a in t.descendants and len(t.select('a[href*="/p/"]')) == 1) or a
                        break
                seen[id(parent)] = parent
            chosen = list(seen.values())
            if chosen:
                res.notes.append("card_selector_fallback_used")
        res.raw_card_count = len(chosen)
        for c in chosen:
            d = _card_dict(c, sel, base_url)
            if d["url"] and d["title"]:
                res.cards.append(d)
            else:
                res.notes.append("card_missing_title_or_url")
    for s in sel.get("next_page") or []:
        try:
            for n in soup.select(s):
                if n.get("disabled") is None and n.get("aria-disabled") != "true":
                    res.has_next = True
        except Exception:
            pass
        if res.has_next:
            break
    main = soup.select_one("main")
    scope_text = " ".join(txt(n) for n in _select(soup, sel.get("results_count"))) or ""
    rx = re.compile(settings.get("declared_total_regex", r"([\d,]+)\s+(?:results|items|products)\b"), re.I)
    m = rx.search(scope_text)
    if m:
        res.declared_total = int(m.group(1).replace(",", ""))
    nr = re.compile(settings.get("no_results_regex", r"no results|0 results"), re.I)
    res.empty_marker = bool(nr.search(txt(main) if main else ""))
    return res


def parse_subcategory_links(html, sel, base_url, parent_url):
    soup = BeautifulSoup(html, "lxml")
    skip = {s.lower() for s in sel.get("subcategory_skip_names", [])}
    excl = set(sel.get("exclude_ancestors", []))
    parent_path = urlsplit(parent_url).path.rstrip("/")
    out, seen = [], set()
    for s in sel.get("subcategory_links") or []:
        try:
            anchors = soup.select(s)
        except Exception:
            continue
        for a in anchors:
            if excl and any(p.name in excl for p in a.parents):
                continue
            href = a.get("href")
            if not href:
                continue
            url = _abs(base_url, href).split("#")[0]
            key = urlsplit(url).path.rstrip("/").lower()
            name = txt(a) or a.get("aria-label", "")
            if not name or name.lower() in skip or key == parent_path.lower() or key in seen:
                continue
            seen.add(key)
            out.append((name, url))
        if out:
            break
    return out


def parse_pdp(html, sel):
    """Product detail page, used for canary products."""
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1")
    title = txt(h1)
    price = ""
    for node in soup.find_all(string=PRICE_RE):
        price = node.strip()
        break
    return {"title": title, "price": fmt_price(price), "banner": parse_banner(soup, sel)[0]}


def with_page(url, page):
    s = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(s.query) if k != "page"]
    if page > 1:
        q.append(("page", str(page)))
    return urlunsplit((s.scheme, s.netloc, s.path, urlencode(q), ""))


def dedupe_key(rec_or_card):
    upc = rec_or_card.get("upc", "")
    return f"upc:{upc}" if upc else f"url:{_href_no_query(rec_or_card.get('url', ''))}"


def is_private_label(title, brand_text, brands):
    hay = f"{brand_text} {title}".lower()
    for b in brands:
        if re.match(rf"\s*{re.escape(b.lower())}\b", brand_text.lower() or "") or re.match(rf"\s*{re.escape(b.lower())}\b", title.lower()):
            return "yes"
    return "no"


def build_record(card, ctx):
    """ctx: dict(location, store, category, sub_category, crawl_date, private_brands).
    Returns (record|None, exclusion_reason|None, unclassified_promos)."""
    if is_approx_weight(card["size"]):
        return None, "approx_weight", []
    d = deals.classify(card["promos"])
    cur, org = fmt_price(card["price_cur"]), fmt_price(card["price_org"])
    if org and cur and org != cur:
        regular, sale = org, cur
    else:
        regular, sale = (cur or org), ""
    st = ctx["store"]
    rec = finalize({
        "zipcode": st["zipcode"], "store_name": st["store_name"], "store_location": st["store_location"],
        "store_logo": st["store_logo"],
        "store_brand": is_private_label(card["title"], card["brand"], ctx["private_brands"]),
        "category": ctx["category"], "sub_category": ctx["sub_category"],
        "product_title": card["title"], "weight": card["size"],
        "regular_price": regular, "sale_price": sale,
        "volume_deals_description": d["volume_deals_description"], "volume_deals_price": d["volume_deals_price"],
        "digital_deals_description": d["digital_deals_description"], "digital_deals_price": d["digital_deals_price"],
        "image_url": card["image_url"], "url": card["url"], "upc": card["upc"], "ppm": card["ppm"],
        "crawl_date": ctx["crawl_date"],
    })
    return rec, None, d["unclassified"]
