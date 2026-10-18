import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from marianos import deals, schema  # noqa: E402
from marianos.common import BlockedError, LockHeld, StoreMismatch, get_logger  # noqa: E402
from marianos.config import Category, Location, load_config  # noqa: E402
from marianos.runner import Crawler  # noqa: E402
from marianos.storage import LocalStorage  # noqa: E402
from fakesite import FakeDriver, FakeSite, make_products  # noqa: E402


def build_cfg():
    cfg = load_config(ROOT / "config")
    S = cfg.settings
    S["pacing"].update(min_delay_s=0, max_delay_s=0)
    S["retries"].update(attempts=2, base_delay_s=0)
    S["block"].update(cooldown_s=0, max_blocks_per_run=1)
    S["validation"]["min_total_records"] = 20
    S["resume"]["max_age_hours"] = 24
    cfg.locations = {"t1": Location(id="t1", zipcode="60607", banner_must_contain=["Roosevelt"])}
    cfg.categories = [Category("Produce", "https://www.marianos.com/d/produce"),
                      Category("Batteries", "https://www.marianos.com/pl/batteries/1?pzn=relevance"),
                      Category("Coupons", "https://www.marianos.com/savings/cl/coupons/")]
    return cfg


def build_site():
    shared = make_products("1", 3)  # appears in two subcategories -> cross-unit duplicate
    fruit = make_products("2", 11) + shared
    veg = make_products("3", 7) + shared
    fruit[1]["size"] = "1 lb approx."                                   # must be excluded
    fruit[2].update(orig="5.99", price="4.99", promos=["2 for $5"])     # sale + volume deal
    fruit[4].update(clip="Clip Coupon: Save $2")                        # digital
    fruit[6].update(promos=["$3.99 each with Digital Coupon"])
    return FakeSite({
        "/d/produce": {"children": [("Fruit", "/pl/fruit/10"), ("Vegetables", "/pl/veg/11")]},
        "/pl/fruit/10": {"products": fruit},
        "/pl/veg/11": {"products": veg},
        "/pl/batteries/1": {"products": make_products("4", 8)},
        "/savings/cl/coupons/": {"coupons": ["Save $1 on Cereal", "Clip: $2 off Detergent"]},
    })


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.st = LocalStorage(self.tmp)
        self.cfg = build_cfg()
        self.log = get_logger("test-silent")
        self.log.handlers.clear()
        self.log.addHandler(__import__("logging").NullHandler())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def crawler(self, site, driver=None):
        d = driver or FakeDriver(site)
        return Crawler(self.cfg, self.cfg.locations["t1"], self.st, d, self.log, sleep=lambda s: None), d

    def latest(self):
        t = self.st.read_text("published/marianos-t1/latest.json")
        return json.loads(t) if t else None


class TestRules(Base):
    def test_field_order_and_blanks(self):
        r = schema.finalize({"product_title": "x", "gupc": "123", "unit_price": "9", "upc": None})
        self.assertEqual(list(r), schema.FIELDS)
        self.assertEqual(r["crawl_date"], "")
        self.assertEqual((r["gupc"], r["unit_price"], r["upc"]), ("", "", ""))
        self.assertNotIn("gupc14", r)
        self.assertNotIn("remarks", r)

    def test_approx(self):
        for t in ["1 lb approx.", "approximately 2 lb", "Avg. 1.5 lb", "~2 lb", "about 3 lb"]:
            self.assertTrue(schema.is_approx_weight(t), t)
        for t in ["12 oz", "1 gal", "6 ct", ""]:
            self.assertFalse(schema.is_approx_weight(t), t)

    def test_deals_brief_examples(self):
        vol = ["2 for $5", "3 for $10", "Buy 1, Get 1 Free", "Buy 2, Get 1 Free", "Mix or Match 5 for $10",
               "Save $5 when you buy 5", "Must buy 4 at $1.99 each"]
        dig = ["Clip Coupon: Save $2", "$3.99 each with Digital Coupon", "Save $5 when you buy 5 with Digital Coupon", "20% off with clipped coupon"]
        for t in vol:
            c = deals.classify([t]); self.assertTrue(c["volume_deals_description"] and not c["digital_deals_description"], t)
        for t in dig:
            c = deals.classify([t]); self.assertTrue(c["digital_deals_description"] and not c["volume_deals_description"], t)
        self.assertEqual(deals.classify(["Buy 1, Get 1 Free"])["volume_deals_price"], "")           # no invented BOGO price
        self.assertEqual(deals.classify(["Clip Coupon: Save $2"])["digital_deals_price"], "")       # no calculated price
        self.assertEqual(deals.classify(["20% off with clipped coupon"])["digital_deals_price"], "")
        self.assertEqual(deals.classify(["Must buy 4 at $1.99 each"])["volume_deals_price"], "1.99")
        self.assertEqual(deals.classify(["$3.99 each with Digital Coupon"])["digital_deals_price"], "3.99")
        self.assertEqual(deals.classify([("Save $1", "digital")])["digital_deals_description"], "Save $1")
        self.assertEqual(deals.classify(["Sale"])["unclassified"], ["Sale"])  # ordinary sale is not a deal


class TestFallbackExtraction(unittest.TestCase):
    def test_unknown_markup_still_parses(self):
        from marianos import extract as X
        sel = load_config(ROOT / "config").selectors
        html = ("<html><body><main><div class='x1'><a href='/p/whole-milk/0001111041600'><h3>Whole Milk</h3></a>"
                "<img src='https://i.example/m.jpg'><div>$2.99</div><div>$0.02/fl oz</div><p>Buy 2, Get 1 Free</p></div>"
                "<div class='x1'><a href='/p/eggs/0001111060903'><h3>Large Eggs 12 ct</h3></a><div>$3.49</div></div></main></body></html>")
        r = X.parse_listing(html, sel, "https://www.marianos.com")
        self.assertEqual(len(r.cards), 2, r.notes)
        c = r.cards[0]
        self.assertEqual((c["title"], c["upc"], c["ppm"]), ("Whole Milk", "0001111041600", "$0.02/fl oz"))
        self.assertIn("$2.99", c["price_cur"])
        self.assertEqual(c["image_url"], "https://i.example/m.jpg")
        self.assertIn("Buy 2, Get 1 Free", c["promos"])
        self.assertEqual(r.cards[1]["upc"], "0001111060903")

    def test_with_page(self):
        from marianos import extract as X
        self.assertEqual(X.with_page("https://x.com/pl/a/1?pzn=relevance", 1), "https://x.com/pl/a/1?pzn=relevance")
        self.assertEqual(X.with_page("https://x.com/pl/a/1?pzn=relevance", 3), "https://x.com/pl/a/1?pzn=relevance&page=3")


class TestEndToEnd(Base):
    def test_happy_path_and_output(self):
        site = build_site()
        c, _ = self.crawler(site)
        out = c.execute()
        self.assertEqual(out["status"], "published", out["issues"])
        ptr = self.latest()
        data = json.loads(self.st.read_text(ptr["dataset_key"]))
        self.assertEqual(len(data), ptr["records"])
        for r in data:
            self.assertEqual(list(r), schema.FIELDS)
            self.assertTrue(all(isinstance(v, str) for v in r.values()))
            self.assertEqual((r["gupc"], r["unit_price"]), ("", ""))
            self.assertEqual(r["zipcode"], "60607")
            self.assertEqual(r["crawl_date"], c.run.m["crawl_date"])
        keys = [r["upc"] or r["url"] for r in data]
        self.assertEqual(len(keys), len(set(keys)))                       # no duplicates
        self.assertFalse([r for r in data if "approx" in r["weight"].lower()])  # approx excluded
        shared = [r for r in data if r["upc"].startswith("00000001")]
        self.assertEqual(len(shared), 3)
        self.assertTrue(all(r["sub_category"] == "Fruit" for r in shared))  # first subcategory wins
        sale = [r for r in data if r["volume_deals_description"] == "2 for $5"][0]
        self.assertEqual((sale["regular_price"], sale["sale_price"], sale["volume_deals_price"]), ("5.99", "4.99", "5.00"))
        self.assertTrue([r for r in data if r["digital_deals_description"].startswith("Clip")])
        self.assertTrue([r for r in data if r["ppm"] == "$0.10/oz" or r["ppm"].startswith("$0.")])
        self.assertTrue([r for r in data if r["store_brand"] == "yes"])
        self.assertTrue([r for r in data if r["category"] == "Coupons"])
        rep = json.loads(self.st.read_text(ptr["report_key"]))
        self.assertEqual(rep["counts"]["excluded_approx_weight"], 1)
        self.assertGreater(rep["counts"]["cross_unit_duplicates_dropped"], 0)
        self.assertEqual(rep["counts"]["duplicates_in_final_dataset"], 0)
        self.assertTrue(rep["store_verification"]["checks_run"] > 5 and not rep["store_verification"]["mismatches"])
        self.assertEqual(len(rep["proof"]["dataset_sha256"]), 64)

    def test_interruption_resumes_without_refetching_done_pages(self):
        site = build_site()
        drv = FakeDriver(site)
        drv.interrupt_after = 14
        c, _ = self.crawler(site, drv)
        with self.assertRaises(KeyboardInterrupt):
            c.execute()
        self.assertIsNone(self.latest())                      # nothing published by a partial run
        calls_before = len(site.calls)
        drv.interrupt_after = None
        c2, _ = self.crawler(site, drv)
        out = c2.execute()
        self.assertEqual(out["status"], "published", out["issues"])
        self.assertEqual(c2.run.m["resumed"], 1)
        clean_site = build_site()
        Crawler(self.cfg, self.cfg.locations["t1"], LocalStorage(tempfile.mkdtemp()), FakeDriver(clean_site), self.log, sleep=lambda s: None).execute()
        # genuine continuation: crash + resume costs about one clean run (+ re-verification overhead), not crash-point + full rerun
        self.assertLessEqual(len(site.calls), len(clean_site.calls) + 4, (len(site.calls), len(clean_site.calls), calls_before))
        # same dataset as an uninterrupted run
        clean_site = build_site()
        st2 = LocalStorage(tempfile.mkdtemp())
        c3 = Crawler(self.cfg, self.cfg.locations["t1"], st2, FakeDriver(clean_site), self.log, sleep=lambda s: None)
        c3.execute()
        a = json.loads(self.st.read_text(self.latest()["dataset_key"]))
        b = json.loads(st2.read_text(json.loads(st2.read_text("published/marianos-t1/latest.json"))["dataset_key"]))
        self.assertEqual(a, b)

    def test_failed_run_never_replaces_good_data(self):
        c, _ = self.crawler(build_site()); c.execute()
        good = self.st.read_text("published/marianos-t1/latest.json")
        good_ds = self.st.read_text(self.latest()["dataset_key"])
        bad = build_site()
        bad.blank_listing = {"/pl/fruit/10", "/pl/veg/11"}   # 200 OK but products vanish (silent block / site change)
        c2, _ = self.crawler(bad)
        out = c2.execute()
        self.assertEqual(out["status"], "rejected")
        self.assertTrue(any("category" in i or "unit" in i or "yield" in i or "below" in i for i in out["issues"]), out["issues"])
        self.assertEqual(self.st.read_text("published/marianos-t1/latest.json"), good)
        self.assertEqual(self.st.read_text(self.latest()["dataset_key"]), good_ds)
        self.assertTrue(self.st.exists(f"rejected/marianos-t1/{c2.run.run_id}/report.json"))

    def test_yield_drop_vs_baseline_rejected(self):
        c, _ = self.crawler(build_site()); c.execute()
        thin = build_site()
        thin.pages["/pl/batteries/1"]["products"] = thin.pages["/pl/batteries/1"]["products"][:2]   # 8 -> 2 products, still "works"
        c2, _ = self.crawler(thin)
        out = c2.execute()
        self.assertEqual(out["status"], "rejected")
        self.assertTrue(any(i.startswith("category_yield_drop:Batteries") for i in out["issues"]), out["issues"])

    def test_store_mismatch_aborts_and_publishes_nothing(self):
        site = build_site()
        site.banner_after_calls = (10, "Mariano's Wrong Store 60000")
        c, _ = self.crawler(site)
        with self.assertRaises(StoreMismatch):
            c.execute()
        self.assertIsNone(self.latest())

    def test_blocked_response_stops_run_resumably(self):
        site = build_site()
        site.status["/pl/veg/11"] = 403
        c, _ = self.crawler(site)
        with self.assertRaises(BlockedError):
            c.execute()
        self.assertIsNone(self.latest())
        m = json.loads(self.st.read_text(f"state/marianos-t1/{c.run.run_id}/manifest.json"))
        self.assertEqual(m["status"], "interrupted")
        site.status.clear()                                    # block lifted -> next run continues the same run
        c2, _ = self.crawler(site)
        self.assertEqual(c2.execute()["status"], "published")
        self.assertEqual(c2.run.run_id, c.run.run_id)

    def test_unverifiable_store_config_fails(self):
        self.cfg.locations["t1"].banner_must_contain = []
        c, _ = self.crawler(build_site())
        with self.assertRaises(StoreMismatch):
            c.execute()

    def test_repeat_run_is_stable_and_uses_canaries(self):
        c, _ = self.crawler(build_site()); c.execute()
        first = self.st.read_text(self.latest()["dataset_key"])
        c2, _ = self.crawler(build_site())
        out = c2.execute()
        self.assertEqual(out["status"], "published", out["issues"])
        self.assertEqual(json.loads(first), json.loads(self.st.read_text(self.latest()["dataset_key"])))
        self.assertEqual(out["report"]["silent_block_detection"]["canaries"][0]["tested"], 10)

    def test_lock_prevents_overlap(self):
        with self.st.lock("marianos-t1"):
            with self.assertRaises(LockHeld):
                with self.st.lock("marianos-t1"):
                    pass
        with self.st.lock("marianos-t1"):   # released afterwards
            pass


class TestFixtureRegression(unittest.TestCase):
    def test_fixtures(self):
        from marianos import extract as X
        sel = load_config(ROOT / "config").selectors
        base = "https://www.marianos.com"
        fix_dir = ROOT / "tests" / "fixtures"

        # 1. listing_deal.html
        html = (fix_dir / "listing_deal.html").read_text(encoding="utf-8")
        lst = X.parse_listing(html, sel, base)
        self.assertIn("Roosevelt", lst.banner)
        self.assertEqual(len(lst.cards), 1)
        c = lst.cards[0]
        self.assertEqual(c["title"], "Organic Whole Milk")
        self.assertEqual(c["upc"], "0001111041600")
        self.assertEqual(c["ppm"], "$0.03/fl oz")
        self.assertIn("2 for $7", c["promos"])

        # 2. pdp.html
        pdp_html = (fix_dir / "pdp.html").read_text(encoding="utf-8")
        pdp = X.parse_pdp(pdp_html, sel)
        self.assertEqual(pdp["title"], "Organic Whole Milk")
        self.assertEqual(pdp["price"], "3.99")

        # 3. department.html
        dept_html = (fix_dir / "department.html").read_text(encoding="utf-8")
        links = X.parse_subcategory_links(dept_html, sel, base, base + "/")
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0][0], "Dairy")

        # 4. empty_results.html
        empty_html = (fix_dir / "empty_results.html").read_text(encoding="utf-8")
        empty_lst = X.parse_listing(empty_html, sel, base)
        self.assertTrue(empty_lst.empty_marker)

        # 5. coupons.html
        coup_html = (fix_dir / "coupons.html").read_text(encoding="utf-8")
        coup_lst = X.parse_listing(coup_html, sel, base, coupons=True)
        self.assertEqual(len(coup_lst.cards), 1)
        self.assertTrue(coup_lst.cards[0].get("coupon"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
