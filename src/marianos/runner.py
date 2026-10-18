"""Run orchestration: lock -> select+verify store -> canaries -> discover -> crawl (checkpointed)
-> assemble -> validate -> publish or reject. A run can never replace published data unless validation passes."""
import hashlib
import json
import random
import re
import time
import uuid
from urllib.parse import urlsplit

from . import extract as X
from .common import (BlockedError, ShapeError, StoreMismatch, TransientError, ev, utcnow, with_retries)
from .guards import check_store, detect_block, looks_like_site
from .report import build_report
from .storage import jdump
from .validate import validate_run


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "x"


class Run:
    def __init__(self, storage, job, run_id, manifest):
        self.st, self.job, self.run_id, self.m = storage, job, run_id, manifest
        self.prefix = f"state/{job}/{run_id}"

    def save(self):
        self.st.write_text(f"{self.prefix}/manifest.json", jdump(self.m))

    def unit_key(self, uid):
        return f"{self.prefix}/units/{uid}.json"

    def load_unit(self, uid):
        t = self.st.read_text(self.unit_key(uid))
        return json.loads(t) if t else None

    def save_unit(self, u):
        self.st.write_text(self.unit_key(u["uid"]), jdump(u))


def load_or_create_run(storage, loc, settings, job, now):
    max_age = settings["resume"]["max_age_hours"] * 3600
    best = None
    for key in storage.list(f"state/{job}/"):
        if key.endswith("/manifest.json"):
            m = json.loads(storage.read_text(key))
            if m.get("status") in ("in_progress", "interrupted") and (now.timestamp() - m["started_ts"]) < max_age:
                if best is None or m["started_ts"] > best["started_ts"]:
                    best = m
    if best:
        run = Run(storage, job, best["run_id"], best)
        run.m["status"] = "in_progress"
        run.m["resumed"] = run.m.get("resumed", 0) + 1
        return run, True
    run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    while storage.exists(f"state/{job}/{run_id}/manifest.json"):  # a fresh run must never inherit another run's checkpoints
        run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    m = {"run_id": run_id, "job": job, "location_id": loc.id, "status": "in_progress",
         "started_at": now.isoformat(timespec="seconds"), "started_ts": now.timestamp(),
         "crawl_date": now.strftime("%Y-%m-%d"), "plan": None, "store": None, "store_checks": [],
         "canaries": [], "blocks": 0, "lat": {"n": 0, "slow": 0, "sum": 0.0, "max": 0.0, "samples": []},
         "notes": [], "errors": [], "resumed": 0, "elapsed_prior_s": 0.0}
    return Run(storage, job, run_id, m), False


class Crawler:
    def __init__(self, cfg, loc, storage, driver, log, sleep=time.sleep, now=None, code_version="dev", only_categories=None, demo=False):
        self.cfg, self.loc, self.st, self.drv, self.log = cfg, loc, storage, driver, log
        self.S, self.sel = cfg.settings, cfg.selectors
        self.sleep = sleep
        self.now = now or utcnow()
        self.job = f"{self.S['retailer']}-{loc.id}"
        self.mult = 1.0
        self.base = self.S["base_url"]
        self.code_version = code_version
        self.only_categories = only_categories
        self.demo = demo

    # ---------- low-level fetch with validation ----------
    def _pace(self):
        p = self.S["pacing"]
        self.sleep(random.uniform(p["min_delay_s"], p["max_delay_s"]) * self.mult)

    def _record_latency(self, s):
        l = self.run.m["lat"]
        l["n"] += 1
        l["sum"] += s
        l["max"] = max(l["max"], s)
        if len(l["samples"]) < 3000:
            l["samples"].append(round(s, 2))
        if s > self.S["pacing"]["slow_page_s"]:
            l["slow"] += 1
            self.mult = min(self.mult * 2, self.S["pacing"]["max_multiplier"])
            ev(self.log, "slow_page_backoff", level="warning", latency_s=round(s, 1), multiplier=self.mult)
        elif self.mult > 1:
            self.mult = max(1.0, self.mult * 0.9)

    def fetch(self, url, coupons=False):
        r_cfg, b_cfg = self.S["retries"], self.S["block"]
        while True:
            def attempt():
                self._pace()
                try:
                    r = self.drv.fetch(url, coupons=coupons)
                except TransientError:
                    raise
                except Exception as e:  # driver/network errors are retryable
                    raise TransientError(f"{type(e).__name__}: {e}")
                self._record_latency(r.latency_s)
                reason = detect_block(r.status, r.html)
                if reason:
                    raise BlockedError(reason)
                if r.status >= 500 or r.status == 408:
                    raise TransientError(f"http {r.status}")
                if r.status >= 400:
                    raise ShapeError(f"http {r.status} for {url}")
                return r
            try:
                return with_retries(attempt, r_cfg["attempts"], r_cfg["base_delay_s"], self.log, "fetch", sleep=self.sleep, url=url)
            except BlockedError as e:
                self.run.m["blocks"] += 1
                ev(self.log, "blocked", level="error", url=url, reason=str(e), blocks=self.run.m["blocks"])
                self.run.save()
                if self.run.m["blocks"] > b_cfg["max_blocks_per_run"]:
                    raise
                self.sleep(b_cfg["cooldown_s"])

    def verified_fetch(self, url, coupons=False):
        r = self.fetch(url, coupons=coupons)
        lst = X.parse_listing(r.html, self.sel, self.base, self.S["crawl"], coupons=coupons)
        self._check_store(lst.banner, url)
        return r, lst

    def _check_store(self, banner, where, cookie=None):
        checks = self.run.m["store_checks"]
        try:
            check_store(banner, self.loc, cookie if cookie is not None else "")
            ok = True
        except StoreMismatch as e:
            checks.append({"ts": utcnow().isoformat(timespec="seconds"), "where": where, "ok": False, "banner": banner, "error": str(e)})
            ev(self.log, "store_mismatch", level="error", where=where, banner=banner, error=str(e))
            raise
        n = self.run.m.setdefault("store_check_count", 0) + 1
        self.run.m["store_check_count"] = n
        if len(checks) < 20 or n % 25 == 0:  # keep the evidence log bounded
            checks.append({"ts": utcnow().isoformat(timespec="seconds"), "where": where, "ok": ok, "banner": banner})

    # ---------- store ----------
    def establish_store(self):
        self.drv.select_store(self.loc)
        r = self.fetch(self.base + "/")
        lst = X.parse_listing(r.html, self.sel, self.base, self.S["crawl"])
        self._check_store(lst.banner, "post-selection home", cookie=self.drv.cookie_blob())
        store = {
            "zipcode": self.loc.zipcode, "store_name": self.loc.store_name or lst.banner,
            "store_location": self.loc.store_location, "store_logo": lst.logo or self.loc.store_logo,
            "banner_text": lst.banner,
        }
        self.run.m["store"] = store
        shot = self.drv.screenshot()
        if shot:
            key = f"evidence/{self.job}/{self.run.run_id}/store_selected.png"
            self.st.write_bytes(key, shot)
            self.run.m["store_evidence"] = key
        ev(self.log, "store_verified", store=self.loc.id, banner=lst.banner)

    # ---------- canaries ----------
    def check_canaries(self, phase):
        urls = list(self.loc.canaries)
        base = self.st.read_text(f"published/{self.job}/canaries.json")
        if base:
            urls += [c["url"] for c in json.loads(base)]
        urls = list(dict.fromkeys(urls))[:10]
        res = {"phase": phase, "tested": 0, "passed": 0, "failures": []}
        for u in urls:
            res["tested"] += 1
            try:
                r = self.fetch(u)
                pdp = X.parse_pdp(r.html, self.sel)
                self._check_store(pdp["banner"], f"canary:{u}")
                if pdp["title"] and pdp["price"]:
                    res["passed"] += 1
                else:
                    res["failures"].append({"url": u, "why": "missing title or price"})
            except (ShapeError, TransientError) as e:
                res["failures"].append({"url": u, "why": str(e)})
        self.run.m["canaries"].append(res)
        ev(self.log, "canaries", phase=phase, tested=res["tested"], passed=res["passed"])

    # ---------- discovery ----------
    def discover(self):
        units, mx = [], self.S["crawl"]["max_depth"]
        categories = self.cfg.categories
        if self.only_categories:
            categories = [c for c in categories if c.name in self.only_categories]
        for cat in categories:
            if cat.kind == "coupons":
                units.append(self._unit(cat, "", cat.url, "coupons"))
                continue
            cat_units, visited = [], {urlsplit(cat.url).path.lower()}

            def walk(url, names, depth):
                r, lst = self.verified_fetch(url)
                links = X.parse_subcategory_links(r.html, self.sel, self.base, url)
                kids = [(n, u) for n, u in links if urlsplit(u).path.lower() not in visited] if depth < mx else []
                for n, u in kids:
                    visited.add(urlsplit(u).path.lower())
                if kids:
                    for n, u in kids:
                        if len(cat_units) >= self.S["crawl"]["max_units_per_category"]:
                            self.run.m["notes"].append(f"max_units_per_category hit for {cat.name}")
                            break
                        walk(u, names + [n], depth + 1)
                else:
                    cat_units.append(self._unit(cat, " > ".join(names), url, "listing"))
                return lst.raw_card_count, bool(kids)

            cards, had_kids = walk(cat.url, [], 0)
            if had_kids and cards:
                cat_units.append(self._unit(cat, "", cat.url, "listing"))  # root last: catch-all, dedupe keeps subcategory label
            units += cat_units
            ev(self.log, "discovered", category=cat.name, units=len(cat_units))
        return units

    def _unit(self, cat, sub, url, kind):
        return {"uid": f"{slug(cat.name)}__{slug(sub)}__{hashlib.sha1(url.encode()).hexdigest()[:8]}",
                "category": cat.name, "sub_category": sub, "url": url, "kind": kind}

    # ---------- crawl one unit (genuine page-level continuation) ----------
    def crawl_unit(self, spec):
        u = self.run.load_unit(spec["uid"]) or {**spec, "status": "pending", "pages_done": 0, "declared_total": None,
                                                 "excluded_approx": 0, "dup_within": 0, "records": [], "seen_keys": [], "errors": [], "unclassified": []}
        if u["status"] in ("done", "empty_confirmed"):
            return u
        u["status"], u["errors"] = "pending", []
        seen, recs = set(u["seen_keys"]), u["records"]
        rec_keys = {X.dedupe_key(r) for r in recs}
        coupons = spec["kind"] == "coupons"
        ctx = {"store": self.run.m["store"], "category": spec["category"], "sub_category": spec["sub_category"],
               "crawl_date": self.run.m["crawl_date"], "private_brands": self.S["private_label_brands"]}
        page = u["pages_done"] + 1
        try:
            while page <= self.S["crawl"]["max_pages_per_unit"]:
                r, lst = self.verified_fetch(X.with_page(spec["url"], page), coupons=coupons)
                if page == 1 and lst.declared_total:
                    u["declared_total"] = lst.declared_total
                if not lst.cards:
                    if page == 1 and not (lst.empty_marker and looks_like_site(r.html, self.S["retailer"])):
                        raise ShapeError("zero products on first page without an explicit empty-state marker")
                    if page == 1:
                        u["status"] = "empty_confirmed"
                    break
                new = 0
                for c in lst.cards:
                    k = X.dedupe_key(c)
                    if k in seen:
                        u["dup_within"] = u.get("dup_within", 0) + 1
                        continue
                    seen.add(k)
                    new += 1
                    rec, why, unc = X.build_record(c, ctx)
                    u["unclassified"] = (u["unclassified"] + unc)[:25]
                    if why:
                        u["excluded_approx"] += 1
                    elif X.dedupe_key(rec) not in rec_keys:
                        rec_keys.add(X.dedupe_key(rec))
                        recs.append(rec)
                u["pages_done"], u["seen_keys"] = page, sorted(seen)
                self.run.save_unit(u)  # checkpoint after every page
                ev(self.log, "page_done", category=spec["category"], sub=spec["sub_category"], page=page,
                   cards=len(lst.cards), new=new, unit_total=len(recs))
                if new == 0:
                    break
                page += 1
            if u["status"] == "pending":
                dt_ = u["declared_total"]
                if dt_ and len(seen) < dt_ * self.S["crawl"]["declared_total_min_ratio"]:
                    u["status"] = "incomplete"
                    u["errors"].append(f"collected {len(seen)} of declared {dt_}")
                else:
                    u["status"] = "done"
        except (ShapeError, TransientError) as e:
            u["status"] = "failed"
            u["errors"].append(f"{type(e).__name__}: {e}")
            ev(self.log, "unit_failed", level="error", category=spec["category"], sub=spec["sub_category"], error=str(e))
        self.run.save_unit(u)
        return u

    # ---------- whole run ----------
    def execute(self):
        S, t0 = self.S, time.time()
        self.run, resumed = load_or_create_run(self.st, self.loc, S, self.job, self.now)
        ev(self.log, "run_start", job=self.job, run_id=self.run.run_id, resumed=resumed, code=self.code_version, demo=self.demo)
        self.run.save()
        try:
            self.establish_store()
            self.check_canaries("start")
            if not self.run.m["plan"]:
                self.run.m["plan"] = self.discover()
                self.run.save()
            plan = self.run.m["plan"]
            for i, spec in enumerate(plan, 1):
                u = self.crawl_unit(spec)
                ev(self.log, "unit_status", n=i, of=len(plan), category=spec["category"], sub=spec["sub_category"],
                   status=u["status"], products=len(u["records"]))
                self.run.save()
            failed = [s for s in plan if (self.run.load_unit(s["uid"]) or {}).get("status") in ("failed", "incomplete")]
            if failed:  # one more pass for failed/incomplete units after a cooldown
                ev(self.log, "retry_failed_units", level="warning", n=len(failed))
                self.sleep(S["block"]["cooldown_s"] / 5)
                for s in failed:
                    self._recrawl(s)
            self.check_canaries("end")
            r = self.fetch(self.base + "/")
            self._check_store(X.parse_listing(r.html, self.sel, self.base, S["crawl"]).banner, "end-of-run home", cookie=self.drv.cookie_blob())
        except BaseException as e:
            self.run.m["status"] = "interrupted"
            self.run.m["errors"].append(f"{type(e).__name__}: {e}")
            self.run.m["elapsed_prior_s"] += time.time() - t0
            self.run.save()
            ev(self.log, "run_interrupted", level="error", error=f"{type(e).__name__}: {e}")
            raise
        self.run.m["elapsed_prior_s"] += time.time() - t0
        return self._finish()

    def _recrawl(self, spec):
        u = self.run.load_unit(spec["uid"])
        if u and u["status"] in ("failed", "incomplete"):
            u["status"] = "pending"
            self.run.save_unit(u)
        return self.crawl_unit(spec)

    # ---------- assemble / validate / publish ----------
    def _finish(self):
        m, S = self.run.m, self.S
        units = [self.run.load_unit(s["uid"]) for s in m["plan"]]
        seen, records, dup_cross = set(), [], 0
        for u in units:
            for rec in u["records"]:
                k = X.dedupe_key(rec)
                if k in seen:
                    dup_cross += 1
                    continue
                seen.add(k)
                records.append(rec)
        base_key = f"demo/{self.job}/latest.json" if self.demo else f"published/{self.job}/latest.json"
        latest = self.st.read_text(base_key) if not self.demo else None
        baseline = None
        if latest:
            ptr = json.loads(latest)
            rt = self.st.read_text(ptr["report_key"])
            baseline = json.loads(rt) if rt else None
        verdict = validate_run(m, units, records, baseline, self.cfg, dup_cross)
        report = build_report(m, units, records, verdict, dup_cross, self.cfg, self.code_version,
                              utcnow(), m["elapsed_prior_s"])
        data = json.dumps(records, ensure_ascii=False, indent=1)
        report["proof"]["dataset_sha256"] = hashlib.sha256(data.encode("utf-8")).hexdigest()
        job, rid = self.job, self.run.run_id
        if verdict["ok"]:
            target_prefix = f"demo/{job}" if self.demo else f"published/{job}"
            dk, rk = f"{target_prefix}/runs/{rid}/dataset.json", f"{target_prefix}/runs/{rid}/report.json"
            self.st.write_text(dk, data)
            self.st.write_text(rk, jdump(report))
            back = self.st.read_text(dk)  # read-back integrity check BEFORE moving the pointer
            if hashlib.sha256(back.encode("utf-8")).hexdigest() != report["proof"]["dataset_sha256"]:
                raise RuntimeError("read-back hash mismatch; latest.json NOT updated")
            if not self.demo:
                self.st.write_text(base_key, jdump({"run_id": rid, "dataset_key": dk, "report_key": rk,
                                                    "published_at": utcnow().isoformat(timespec="seconds"),
                                                    "records": len(records), "sha256": report["proof"]["dataset_sha256"]}))
                sample = random.Random(rid).sample(records, min(10, len(records)))
                self.st.write_text(f"published/{job}/canaries.json", jdump([{"url": r["url"], "title": r["product_title"], "upc": r["upc"]} for r in sample]))
                self._prune(job)
            m["status"] = "published"
        else:
            rej_prefix = f"demo/{job}/rejected/{rid}" if self.demo else f"rejected/{job}/{rid}"
            self.st.write_text(f"{rej_prefix}/dataset.json", data)
            self.st.write_text(f"{rej_prefix}/report.json", jdump(report))
            m["status"] = "rejected"
        self.run.save()
        ev(self.log, "run_final", status=m["status"], records=len(records), issues=verdict["issues"], warnings=verdict["warnings"])
        return {"status": m["status"], "records": len(records), "issues": verdict["issues"], "report": report}

    def _prune(self, job):
        keep = self.S["publish"]["keep_history"]
        runs = sorted({k.split("/")[3] for k in self.st.list(f"published/{job}/runs/")})
        for rid in runs[:-keep]:
            for k in self.st.list(f"published/{job}/runs/{rid}/"):
                self.st.delete(k)
