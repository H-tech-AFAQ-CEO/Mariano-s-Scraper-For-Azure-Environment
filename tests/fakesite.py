"""SYNTHETIC site + driver for offline logic tests. This does NOT represent Mariano's real markup."""
import re
from urllib.parse import urlsplit, parse_qs

from marianos.driver import FetchResult

BANNER_OK = "Mariano's Roosevelt Rd 60607"


def card(p):
    price = f'<mark data-testid="cart-page-item-unit-price">${p["price"]}</mark>'
    if p.get("orig"):
        price += f'<s>${p["orig"]}</s>'
    promo = "".join(f'<span data-testid="promo-badge">{t}</span>' for t in p.get("promos", []))
    clip = f'<button data-testid="coupon-clip">{p["clip"]}</button>' if p.get("clip") else ""
    ppm = f'<span data-testid="price-per-unit">{p["ppm"]}</span>' if p.get("ppm") else ""
    return (f'<div data-testid="auto-grid-cell"><a href="/p/{p["slug"]}/{p["upc"]}"><span data-testid="cart-page-item-description">{p["title"]}</span></a>'
            f'<img src="https://img.example.com/{p["upc"]}.jpg"><span data-testid="cart-page-item-sizing">{p["size"]}</span>{price}{ppm}{promo}{clip}</div>')


def make_products(prefix, n, start=0):
    out = []
    for i in range(start, start + n):
        upc = f"{int(prefix) * 100000 + i:013d}"
        out.append({"slug": f"item-{upc}", "upc": upc, "title": f"{'Kroger ' if i % 4 == 0 else ''}Item {prefix}-{i}", "size": "12 oz",
                    "price": f"{2 + i % 7}.49", "ppm": f"$0.{10 + i % 80}/oz" if i % 2 == 0 else ""})
    return out


class FakeSite:
    """pages: path -> {'products': [...], 'page_size': int, 'children': [(name, path)], 'coupons': [...]}"""

    def __init__(self, pages, banner=BANNER_OK, page_size=5):
        self.pages, self.banner, self.page_size = pages, banner, page_size
        self.calls = []
        self.status = {}          # path -> status override
        self.blank_listing = set()
        self.banner_after_calls = None   # (n, banner) switches banner after n fetches

    def html(self, body, total=None):
        pad = "<!-- marianos " + "x" * 4500 + " -->"
        return (f'<html><body><header><button data-testid="CurrentModality-button">{self.banner}</button>'
                f'<a href="/"><img alt="Mariano\'s" src="https://img.example.com/logo.png"></a></header><main>{body}</main>{pad}</body></html>')

    def get(self, url, coupons=False):
        self.calls.append(url)
        if self.banner_after_calls and len(self.calls) > self.banner_after_calls[0]:
            self.banner = self.banner_after_calls[1]
        s = urlsplit(url)
        path, q = s.path, parse_qs(s.query)
        page = int(q.get("page", ["1"])[0])
        if path in self.status:
            return FetchResult(self.status[path], "<html>Access Denied</html>" if self.status[path] == 403 else "", 0.1, url)
        pg = self.pages.get(path)
        if path.startswith("/p/"):
            return FetchResult(200, self.html('<h1>Some product</h1><span>$3.49</span>'), 0.1, url)
        if path in ("", "/"):
            return FetchResult(200, self.html("<h1>Home</h1>"), 0.1, url)
        if pg is None:
            return FetchResult(404, "", 0.1, url)
        body = ""
        for name, child in pg.get("children", []):
            body += f'<a href="{child}">{name}</a>'
        if pg.get("coupons"):
            body += "".join(f'<div data-testid="coupon-card"><h3>{c}</h3><a href="/savings/cl/coupon/{i}">x</a></div>' for i, c in enumerate(pg["coupons"]))
        prods = pg.get("products", [])
        if path in self.blank_listing:
            prods = []
        if prods:
            ps = self.page_size
            chunk = prods[(page - 1) * ps: page * ps]
            body += f'<div data-testid="result-count">{len(prods)} results</div>' + "".join(card(p) for p in chunk)
            if page * ps < len(prods):
                body += f'<a rel="next" href="{path}?page={page + 1}">Next</a>'
        elif not pg.get("children") and not pg.get("coupons") and path not in self.blank_listing:
            body += "<p>No results found</p>"
        return FetchResult(200, self.html(body), 0.1, url)


class FakeDriver:
    def __init__(self, site):
        self.site = site
        self.interrupt_after = None

    def __enter__(self): return self
    def __exit__(self, *a): pass
    def select_store(self, loc): pass
    def cookie_blob(self): return ""
    def screenshot(self): return b"\x89PNG-fake"

    def fetch(self, url, coupons=False):
        if self.interrupt_after is not None and len(self.site.calls) >= self.interrupt_after:
            raise KeyboardInterrupt("simulated crash")
        return self.site.get(url, coupons)
