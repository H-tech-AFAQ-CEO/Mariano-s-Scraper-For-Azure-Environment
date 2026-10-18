"""Run report = the contest evidence pack (counts, runtime, completeness, examples, store proof, provenance)."""
import hashlib
import platform
import socket
import sys
from collections import Counter

from .validate import completeness, pct


def _file_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return ""


def build_report(m, units, records, verdict, dup_cross, cfg, code_version, finished_at, runtime_s):
    by_cat = Counter(r["category"] for r in records)
    by_sub = Counter((r["category"], r["sub_category"]) for r in records)
    dup_within = sum(u.get("dup_within", 0) for u in units)
    excluded = sum(u["excluded_approx"] for u in units)
    ex = lambda pred, n=5: [r for r in records if pred(r)][:n]
    examples = {
        "ppm": ex(lambda r: r["ppm"]),
        "volume_deals": ex(lambda r: r["volume_deals_description"]),
        "digital_deals": ex(lambda r: r["digital_deals_description"]),
        "no_deals": ex(lambda r: not r["volume_deals_description"] and not r["digital_deals_description"]),
        "sale_price": ex(lambda r: r["sale_price"]),
    }
    lat = sorted(m["lat"]["samples"])
    unclassified = Counter(t for u in units for t in u.get("unclassified", []))
    cdir = cfg.config_dir
    return {
        "run_id": m["run_id"], "location_id": m["location_id"], "crawl_date": m["crawl_date"],
        "started_at": m["started_at"], "finished_at": finished_at.isoformat(timespec="seconds"),
        "runtime_seconds": round(runtime_s, 1), "resumed_times": m.get("resumed", 0),
        "validation": {"ok": verdict["ok"], "issues": verdict["issues"], "warnings": verdict["warnings"]},
        "counts": {
            "total_unique": len(records),
            "by_category": dict(by_cat),
            "raw_by_category": verdict["raw_by_category"],
            "by_sub_category": {f"{c} | {s}": n for (c, s), n in by_sub.items()},
            "within_unit_duplicates_dropped": dup_within,
            "cross_unit_duplicates_dropped": dup_cross,
            "duplicates_in_final_dataset": len(records) - len({r["upc"] or r["url"].split("?")[0] for r in records}),
            "excluded_approx_weight": excluded,
            "units_total": len(units),
            "units_by_status": dict(Counter(u["status"] for u in units)),
        },
        "completeness": verdict["completeness"],
        "category_coverage": [
            {"category": u["category"], "sub_category": u["sub_category"], "status": u["status"], "pages": u["pages_done"],
             "products": len(u["records"]), "seen_incl_excluded": len(u["seen_keys"]),
             "declared_total": u["declared_total"], "errors": u["errors"]} for u in units],
        "examples": examples,
        "store_verification": {
            "configured_location": m["location_id"], "banner_text": (m.get("store") or {}).get("banner_text"),
            "checks_run": m.get("store_check_count", 0), "mismatches": [c for c in m["store_checks"] if not c["ok"]],
            "sample_checks": m["store_checks"][:5], "evidence_screenshot": m.get("store_evidence"),
        },
        "silent_block_detection": {
            "canaries": m["canaries"], "block_events": m["blocks"],
            "latency_s": {"pages": m["lat"]["n"], "slow_pages": m["lat"]["slow"], "p50": pct(lat, .5), "p95": pct(lat, .95), "max": m["lat"]["max"]},
        },
        "unclassified_promo_text_top": unclassified.most_common(15),
        "notes": m["notes"], "errors": m["errors"],
        "proof": {
            "scraper_version": code_version, "host": socket.gethostname(), "python": sys.version.split()[0],
            "platform": platform.platform(), "config_hashes": {n: _file_hash(cdir / n) for n in ("settings.yaml", "selectors.yaml", "locations.yaml", "categories.csv")},
            "dataset_sha256": "",
        },
    }
