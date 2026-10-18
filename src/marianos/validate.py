"""Run-level validation. Any entry in `issues` blocks publication; `warnings` are reported only."""
from collections import Counter, defaultdict

from .extract import dedupe_key
from .schema import FIELDS, check_record_shape, is_approx_weight


def completeness(records):
    n = len(records) or 1
    out = {f: round(sum(1 for r in records if r[f] != "") / n, 4) for f in FIELDS}
    out["price_any"] = round(sum(1 for r in records if r["regular_price"] or r["sale_price"]) / n, 4)
    return out


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    return sorted_vals[min(len(sorted_vals) - 1, int(len(sorted_vals) * p))]


def validate_run(manifest, units, records, baseline, cfg, dup_cross):
    V = cfg.settings["validation"]
    issues, warnings = [], []
    # --- location
    mism = [c for c in manifest["store_checks"] if not c["ok"]]
    if mism:
        issues.append(f"store_mismatch_events:{len(mism)}")
    if not manifest.get("store_check_count"):
        issues.append("store_never_verified")
    # --- categories: every CSV category present, no failed units, no zero-by-failure
    by_cat_units = defaultdict(list)
    for u in units:
        by_cat_units[u["category"]].append(u)
    for c in cfg.categories:
        if c.name not in by_cat_units:
            issues.append(f"missing_category:{c.name}")
    failed = [u for u in units if u["status"] in ("failed", "incomplete")]
    if len(failed) > V["max_failed_units"]:
        issues.append(f"failed_or_incomplete_units:{len(failed)}")
    raw_by_cat = {c: sum(len(u["records"]) for u in us) for c, us in by_cat_units.items()}
    base_cat = (baseline or {}).get("counts", {}).get("raw_by_category", {})
    for c, n in raw_by_cat.items():
        all_empty = all(u["status"] == "empty_confirmed" for u in by_cat_units[c])
        if n == 0 and not all_empty:
            issues.append(f"category_zero_products:{c}")
        elif baseline:
            b = base_cat.get(c)
            if b and n < b * V["yield_min_ratio"]:
                issues.append(f"category_yield_drop:{c}:{n}<{V['yield_min_ratio']}x{b}")
        elif n < V["min_unit_records_first_run"] and not all_empty:
            issues.append(f"category_thin_first_run:{c}")
    # --- total
    if len(records) < V["min_total_records"]:
        issues.append(f"total_below_minimum:{len(records)}<{V['min_total_records']}")
    if baseline:
        bt = baseline["counts"]["total_unique"]
        if len(records) < bt * V["total_yield_min_ratio"]:
            issues.append(f"total_yield_drop:{len(records)}<{V['total_yield_min_ratio']}x{bt}")
    else:
        warnings.append("no_baseline_first_successful_run")
    # --- schema / data rules
    shape = Counter()
    for r in records:
        for p in check_record_shape(r):
            shape[p] += 1
    if shape:
        issues.append(f"schema_violations:{dict(shape)}")
    if sum(1 for r in records if is_approx_weight(r["weight"])):
        issues.append("approx_weight_records_present")
    keys = [dedupe_key(r) for r in records]
    if len(keys) != len(set(keys)):
        issues.append("duplicates_in_final_dataset")
    coupon_cats = {c.name for c in cfg.categories if c.kind == "coupons"}
    comp = completeness([r for r in records if r["category"] not in coupon_cats])  # coupon cards have no price/UPC/weight
    for f, mn in V["completeness_min"].items():
        if comp.get(f, 0) < mn:
            issues.append(f"completeness_below_min:{f}:{comp.get(f, 0)}<{mn}")
    # --- silent-block signals
    lat = manifest["lat"]
    if lat["n"] and lat["slow"] / lat["n"] > V["max_slow_page_fraction"]:
        issues.append(f"abnormal_latency:{lat['slow']}/{lat['n']}")
    tested = sum(c["tested"] for c in manifest["canaries"])
    passed = sum(c["passed"] for c in manifest["canaries"])
    if tested == 0:
        warnings.append("no_canaries_available")
    elif passed / tested < V["canary_min_pass_ratio"]:
        issues.append(f"canary_failures:{passed}/{tested}")
    if manifest["blocks"]:
        warnings.append(f"block_events:{manifest['blocks']}")
    return {"ok": not issues, "issues": issues, "warnings": warnings, "completeness": comp,
            "raw_by_category": raw_by_cat, "canaries": {"tested": tested, "passed": passed}}
