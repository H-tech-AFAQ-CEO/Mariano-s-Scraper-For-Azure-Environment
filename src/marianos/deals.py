"""Volume vs digital deal classification. Preserves retailer wording; never calculates a price."""
import re

DIGITAL_RE = re.compile(
    r"\b(clip(?:ped)?|digital\s+coupon|e-?coupon|activate[d]?|load\s+to\s+card|add\s+(?:the\s+)?(?:coupon|offer)|with\s+coupon|coupon)\b",
    re.I,
)
VOLUME_RE = re.compile(
    r"(\b\d+\s*for\s*\$\s*\d|\bbuy\s*\d+|\bb\.?o\.?g\.?o\b|\bmix\s*(?:or|&|and)\s*match|\bmust\s*buy\s*\d+|\bwhen\s+you\s+buy\s*\d+|\bget\s+\d+\s+free|\b\d+\s*/\s*\$\s*\d)",
    re.I,
)
# Displayed promotional prices only. "Save $X" is deliberately NOT matched.
_PRICE_PATTERNS = [
    re.compile(r"\b\d+\s*for\s*\$\s*(\d+(?:\.\d{1,2})?)", re.I),                      # 2 for $5 / Mix or Match 5 for $10
    re.compile(r"\b\d+\s*/\s*\$\s*(\d+(?:\.\d{1,2})?)", re.I),                         # 2/$5
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s*(?:each|/\s*ea\b|ea\b)", re.I),            # $1.99 each / $3.99 each with Digital Coupon
    re.compile(r"\bmust\s*buy\s*\d+\s*(?:at|:|-)?\s*\$\s*(\d+(?:\.\d{1,2})?)", re.I),  # Must buy 4 at $1.99
    re.compile(r"\bat\s*\$\s*(\d+(?:\.\d{1,2})?)", re.I),                              # at $1.99
]


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def displayed_price(text: str) -> str:
    for p in _PRICE_PATTERNS:
        m = p.search(text)
        if m:
            return f"{float(m.group(1)):.2f}"
    return ""


def is_deal_text(text: str) -> bool:
    return bool(DIGITAL_RE.search(text) or VOLUME_RE.search(text))


def classify(texts):
    """texts: promo strings found on a product card.
    Digital wins when clip/activation wording is present (a loyalty card alone never makes it digital)."""
    seen, vol, dig, unclassified = set(), [], [], []
    for item in texts:
        # item is "text" or ("text", "digital"|"volume") when the DOM element itself says which it is
        raw, hint = (item if isinstance(item, tuple) else (item, ""))
        t = clean(raw)
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        if hint == "digital" or DIGITAL_RE.search(t):
            dig.append(t)
        elif VOLUME_RE.search(t):
            vol.append(t)
        else:
            unclassified.append(t)
    vp = next((displayed_price(t) for t in vol if displayed_price(t)), "")
    dp = next((displayed_price(t) for t in dig if displayed_price(t)), "")
    return {
        "volume_deals_description": " | ".join(vol),
        "volume_deals_price": vp,
        "digital_deals_description": " | ".join(dig),
        "digital_deals_price": dp,
        "unclassified": unclassified,
    }
