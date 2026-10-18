"""Independent acceptance checker for a dataset JSON:  python -m marianos.check_output dataset.json
Re-verifies schema/field order, empty-string policy, duplicates, approx weights, deal/PPM rules and prints completeness + category counts."""
import json
import sys
from collections import Counter

from .extract import dedupe_key
from .schema import FIELDS, check_record_shape, is_approx_weight
from .validate import completeness


def main(path):
    data = json.load(open(path, encoding="utf-8"))
    bad = Counter()
    for r in data:
        for p in check_record_shape(r):
            bad[p] += 1
        if is_approx_weight(r.get("weight", "")):
            bad["approx_weight"] += 1
        if r.get("digital_deals_price") and not r.get("digital_deals_description"):
            bad["digital_price_without_description"] += 1
        if r.get("volume_deals_price") and not r.get("volume_deals_description"):
            bad["volume_price_without_description"] += 1
    keys = [dedupe_key(r) for r in data]
    print(f"records={len(data)} unique_keys={len(set(keys))} duplicates={len(keys) - len(set(keys))}")
    print("by_category:", dict(Counter(r["category"] for r in data)))
    print("completeness:", completeness(data))
    print("violations:", dict(bad) or "none")
    print("fields:", "OK" if data and list(data[0]) == FIELDS else "MISMATCH")
    return 1 if bad or len(keys) != len(set(keys)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
