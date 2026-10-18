"""CLI:  run | status | doctor | discover | verify-store | reset
Exit codes: 0 published, 2 run finished but REJECTED by validation (previous data untouched),
            1 error/interrupted (checkpoint kept; next run resumes), 3 another run holds the lock (skipped)."""
import argparse
import json
import os
import sys

from . import __version__
from .common import LockHeld, ev, get_logger
from .config import load_config
from .storage import make_storage


def _code_version():
    return os.getenv("CODE_VERSION", __version__)


def cmd_run(a):
    cfg = load_config(a.config_dir)
    storage = make_storage(cfg.settings)
    log = get_logger(log_file=os.getenv("MARIANOS_LOG_FILE"))
    ids = [l.id for l in cfg.locations.values() if l.enabled] if a.all else [a.location]
    worst = 0
    from .driver import PlaywrightDriver
    from .runner import Crawler
    for lid in ids:
        loc = cfg.locations[lid]
        job = f"{cfg.settings['retailer']}-{lid}"
        try:
            with storage.lock(job):
                with PlaywrightDriver(cfg, log) as drv:
                    out = Crawler(cfg, loc, storage, drv, log, code_version=_code_version(),
                                  only_categories=a.only_category, demo=a.demo).execute()
            worst = max(worst, 2 if out["status"] == "rejected" else 0)
        except LockHeld as e:
            ev(log, "skipped_lock_held", level="warning", job=job, error=str(e))
            worst = max(worst, 3 if worst == 0 else worst)
        except Exception as e:
            ev(log, "run_failed", level="error", job=job, error=f"{type(e).__name__}: {e}")
            worst = 1
    return worst


def cmd_status(a):
    cfg = load_config(a.config_dir)
    st = make_storage(cfg.settings)
    job = f"{cfg.settings['retailer']}-{a.location}"
    print(st.read_text(f"published/{job}/latest.json") or "no successful run published yet")
    return 0


def cmd_doctor(a):
    """Live self-check: select store, verify banner, count selector hits, show parsed cards + discovered subcategories."""
    from . import extract as X
    from .driver import PlaywrightDriver
    cfg = load_config(a.config_dir)
    log = get_logger()
    loc = cfg.locations[a.location]
    url = a.url or cfg.categories[1].url
    os.makedirs("doctor_out", exist_ok=True)
    with PlaywrightDriver(cfg, log) as drv:
        drv.select_store(loc)
        r = drv.fetch(url)
        open("doctor_out/page.html", "w", encoding="utf-8").write(r.html)
        png = drv.screenshot()
        if png:
            open("doctor_out/header.png", "wb").write(png)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.html, "lxml")
    print(f"status={r.status} latency={r.latency_s:.1f}s html_bytes={len(r.html)}")
    for key in ("store_banner", "card", "title", "size", "price_current", "price_original", "ppm", "promo", "promo_digital", "next_page", "subcategory_links"):
        print(f"{key:18s}", [(s, len(soup.select(s))) for s in cfg.selectors.get(key, [])])
    lst = X.parse_listing(r.html, cfg.selectors, cfg.settings["base_url"], cfg.settings["crawl"])
    print("banner:", lst.banner, "| cards:", len(lst.cards), "| declared_total:", lst.declared_total, "| has_next:", lst.has_next, "| notes:", lst.notes)
    for c in lst.cards[:3]:
        print(json.dumps(c, ensure_ascii=False)[:400])
    print("subcategories:", X.parse_subcategory_links(r.html, cfg.selectors, cfg.settings["base_url"], url)[:15])
    print("Saved doctor_out/page.html and header.png for selector tuning.")
    return 0


def cmd_discover(a):
    """Print the discovered category -> subcategory -> URL tree without scraping products."""
    cfg = load_config(a.config_dir)
    log = get_logger()
    loc = cfg.locations[a.location]
    from .driver import PlaywrightDriver
    from .runner import Crawler
    with PlaywrightDriver(cfg, log) as drv:
        crawler = Crawler(cfg, loc, make_storage(cfg.settings), drv, log, code_version=_code_version())
        crawler.drv.select_store(loc)
        units = crawler.discover()
    tree = {}
    for u in units:
        tree.setdefault(u["category"], []).append((u["sub_category"], u["url"]))
    for cat, subs in tree.items():
        print(f"Category: {cat}")
        for sub, url in subs:
            print(f"  -> {sub or '(root)'} : {url}")
    return 0


def cmd_verify_store(a):
    """Smoke command that selects store and prints store verification evidence."""
    cfg = load_config(a.config_dir)
    log = get_logger()
    loc = cfg.locations[a.location]
    from .driver import PlaywrightDriver
    from .guards import check_store
    from .extract import parse_listing
    with PlaywrightDriver(cfg, log) as drv:
        drv.select_store(loc)
        r = drv.fetch(cfg.settings["base_url"] + "/")
        lst = parse_listing(r.html, cfg.selectors, cfg.settings["base_url"], cfg.settings["crawl"])
        print(f"Store banner found: {lst.banner}")
        print(f"Store logo found: {lst.logo}")
        try:
            check_store(lst.banner, loc, drv.cookie_blob())
            print("Store verification: PASSED (banner matches banner_must_contain)")
        except Exception as e:
            print(f"Store verification: FAILED ({e})")
            return 1
    return 0


def cmd_reset(a):
    """Abandon an unfinished run state for a location."""
    cfg = load_config(a.config_dir)
    st = make_storage(cfg.settings)
    job = f"{cfg.settings['retailer']}-{a.location}"
    prefix = f"state/{job}/"
    keys = st.list(prefix)
    print(f"Found {len(keys)} state files for job {job}.")
    if not keys:
        print("No active run state to reset.")
        return 0
    if not a.yes:
        ans = input("Are you sure you want to abandon/reset unfinished run state? [y/N]: ")
        if ans.lower() not in ("y", "yes"):
            print("Aborted.")
            return 0
    for k in keys:
        st.delete(k)
    print(f"Reset complete. Deleted {len(keys)} state files.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="marianos")
    p.add_argument("--config-dir", default=os.getenv("MARIANOS_CONFIG_DIR", "config"))
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--location")
    g.add_argument("--all", action="store_true")
    r.add_argument("--only-category", action="append", help="Run only specific category name(s)")
    r.add_argument("--demo", action="store_true", help="Demo mode: write to demo/ instead of published/")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("status")
    s.add_argument("--location", required=True)
    s.set_defaults(fn=cmd_status)

    d = sub.add_parser("doctor")
    d.add_argument("--location", required=True)
    d.add_argument("--url")
    d.set_defaults(fn=cmd_doctor)

    disc = sub.add_parser("discover")
    disc.add_argument("--location", required=True)
    disc.set_defaults(fn=cmd_discover)

    vs = sub.add_parser("verify-store")
    vs.add_argument("--location", required=True)
    vs.set_defaults(fn=cmd_verify_store)

    rst = sub.add_parser("reset")
    rst.add_argument("--location", required=True)
    rst.add_argument("--yes", action="store_true", help="Confirm reset without prompt")
    rst.set_defaults(fn=cmd_reset)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
