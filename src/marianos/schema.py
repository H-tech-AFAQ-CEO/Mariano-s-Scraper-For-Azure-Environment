"""Output schema: exact field order, empty-string policy, price formatting, approx-weight rule."""
import re
from decimal import Decimal, InvalidOperation

FIELDS = [
    "zipcode", "store_name", "store_location", "store_logo", "store_brand",
    "category", "sub_category", "product_title", "weight",
    "regular_price", "sale_price",
    "volume_deals_description", "volume_deals_price",
    "digital_deals_description", "digital_deals_price",
    "image_url", "url", "upc", "gupc", "ppm", "unit_price", "crawl_date",
]
assert len(FIELDS) == 22 and FIELDS[-1] == "crawl_date"

# approx / approximately / avg / average / about / est. / ~ / ≈ ...
APPROX_RE = re.compile(
    r"\b(approx(?:imate(?:ly)?)?\.?|apx|avg\.?|average|about|around|est(?:imated)?\.?)\b|[~≈]",
    re.I,
)


def is_approx_weight(text: str) -> bool:
    return bool(text and APPROX_RE.search(text))


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def fmt_price(text) -> str:
    """'$3.5 /ea' -> '3.50'. Returns '' when no number is present. Never calculates anything."""
    if text is None:
        return ""
    m = _NUM.search(str(text))
    if not m:
        return ""
    try:
        return str(Decimal(m.group(0).replace(",", "")).quantize(Decimal("0.01")))
    except InvalidOperation:
        return ""


def finalize(raw: dict) -> dict:
    """Return the record with exactly FIELDS in order, all strings, gupc/unit_price forced empty."""
    out = {}
    for f in FIELDS:
        v = raw.get(f)
        out[f] = "" if v is None else str(v).strip()
    out["gupc"] = ""          # never scraped / generated at this stage
    out["unit_price"] = ""    # calculated later by downstream pipeline
    return out


def check_record_shape(rec: dict) -> list:
    problems = []
    if list(rec.keys()) != FIELDS:
        problems.append("field_order_or_set_mismatch")
    for k, v in rec.items():
        if not isinstance(v, str):
            problems.append(f"non_string:{k}")
    if rec.get("gupc") != "":
        problems.append("gupc_not_empty")
    if rec.get("unit_price") != "":
        problems.append("unit_price_not_empty")
    return problems
