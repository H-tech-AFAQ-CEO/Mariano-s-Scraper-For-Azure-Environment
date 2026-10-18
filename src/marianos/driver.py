"""Playwright driver. Standard Chromium via Playwright only: no stealth plugins, no CAPTCHA solving,
no fingerprint spoofing. If the site challenges the scraper the run stops and is resumable."""
import json
import re
import time
from dataclasses import dataclass
from urllib.parse import quote, unquote

from .common import TransientError, ev
from .config import proxy_from_env


@dataclass
class FetchResult:
    status: int
    html: str
    latency_s: float
    final_url: str


class PlaywrightDriver:
    def __init__(self, cfg, log):
        self.cfg, self.log, self.S, self.sel = cfg, log, cfg.settings, cfg.selectors
        self.base = self.S["base_url"]

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        b = self.S["browser"]
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=b["headless"], proxy=proxy_from_env(), args=["--disable-http2"])
        kw = dict(locale=b["locale"], timezone_id=b["timezone"], viewport=b["viewport"])
        if b.get("user_agent"):
            kw["user_agent"] = b["user_agent"]
        self.context = self.browser.new_context(**kw)
        self.context.set_default_timeout(b["nav_timeout_ms"])
        self.page = self.context.new_page()
        return self

    def __exit__(self, *a):
        for c in (getattr(self, "context", None), getattr(self, "browser", None)):
            try:
                c and c.close()
            except Exception:
                pass
        try:
            self._pw.stop()
        except Exception:
            pass

    def _goto(self, url):
        from playwright.sync_api import TimeoutError as PWTimeout, Error as PWError
        try:
            return self.page.goto(url, wait_until="domcontentloaded", timeout=self.S["browser"]["nav_timeout_ms"])
        except (PWTimeout, PWError) as e:
            raise TransientError(f"navigation failed: {e}")

    def select_store(self, loc):
        """Selects the store by details URL (preferred) or by ZIP search + matching the configured tokens.
        Success is NOT assumed: the runner verifies the header banner afterwards and fails the run on mismatch."""
        url = loc.store_details_url or f"{self.base}/stores/search?searchText={quote(loc.zipcode)}"
        self._goto(url)
        self.page.wait_for_timeout(2500)
        btn = re.compile(r"shop (?:this )?store|select store|make this my store|shop at this store", re.I)
        scope = self.page
        if not loc.store_details_url and loc.banner_must_contain:
            cont = self.page.locator("li, article, div[data-testid*='store' i]").filter(
                has_text=re.compile(re.escape(loc.banner_must_contain[0]), re.I))
            if cont.count():
                scope = cont.first
        target = scope.get_by_role("button", name=btn)
        if not target.count():
            target = scope.get_by_role("link", name=btn)
        if not target.count():
            raise TransientError("store select button not found; run `doctor` and adjust select logic/selectors")
        target.first.click()
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(3000)
        ev(self.log, "store_select_clicked", store=loc.id)

    def _card_css(self, coupons):
        sels = (self.sel.get("coupon_card") if coupons else self.sel.get("card")) or []
        return sels[0] if sels else "a[href*='/p/']"

    def fetch(self, url, coupons=False):
        from playwright.sync_api import TimeoutError as PWTimeout
        S, t0 = self.S, time.time()
        resp = self._goto(url)
        status = resp.status if resp else 0
        wait = ", ".join((self.sel.get("coupon_card") if coupons else self.sel.get("card")) or []) or "main"
        try:
            self.page.wait_for_selector(f"{wait}, h1, main", timeout=20000)
        except PWTimeout:
            pass
        if status < 400:
            self._lazy_load(coupons)
        html = self.page.content()
        return FetchResult(status, html, time.time() - t0, self.page.url)

    def _lazy_load(self, coupons):
        c = S = self.S["crawl"]
        css, stable, last = self._card_css(coupons), 0, -1
        more = (self.sel.get("load_more") or [None])[0]
        for _ in range(c["lazy_scroll_rounds"]):
            try:
                self.page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 0.9))")
                self.page.wait_for_timeout(500)
                if more:
                    lm = self.page.locator(more)
                    if lm.count() and lm.first.is_visible():
                        lm.first.click()
                        self.page.wait_for_timeout(1200)
                n = self.page.locator(css).count()
            except Exception:
                break
            at_bottom = self.page.evaluate("window.innerHeight + window.scrollY >= document.body.scrollHeight - 4")
            stable = stable + 1 if (n == last and at_bottom) else 0
            last = n
            if stable >= c["lazy_stable_rounds"]:
                break

    def cookie_blob(self):
        try:
            return unquote(json.dumps(self.context.cookies()))
        except Exception:
            return ""

    def screenshot(self):
        try:
            return self.page.screenshot(clip={"x": 0, "y": 0, "width": 1366, "height": 160})
        except Exception:
            return None
