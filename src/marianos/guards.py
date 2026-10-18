"""Silent-blocking / shape detection and store matching."""
import re

from .common import StoreMismatch

BLOCK_MARKERS = re.compile(
    r"access denied|pardon our interruption|px-captcha|are you (?:a )?human|unusual traffic|"
    r"verify you are (?:a )?human|_incapsula_|request unsuccessful|errors\.edgesuite\.net|"
    r"reference\s*#\s*[\d.a-f]+|enable javascript and cookies|attention required",
    re.I,
)


def detect_block(status, html):
    """Returns a reason string if the response is a block/challenge, else None."""
    if status in (401, 403, 429):
        return f"http_{status}"
    head = (html or "")[:30000]
    if BLOCK_MARKERS.search(head) and len(html or "") < 60000:
        return "challenge_page_markers"
    return None


def looks_like_site(html, retailer="marianos"):
    h = (html or "")
    return len(h) > 4000 and retailer in h.lower()


def check_store(banner, loc, cookie_blob=""):
    """The configured store must be the one displayed. Raises StoreMismatch otherwise.
    banner_must_contain: ALL tokens must appear in the header store banner.
    store_id (if configured): must appear in the store cookie/storage blob."""
    if not loc.banner_must_contain:
        raise StoreMismatch(f"location '{loc.id}' has no banner_must_contain tokens - store cannot be verified")
    b = (banner or "").lower()
    if not b:
        raise StoreMismatch("no store banner found on page (not logged to a store, or selector changed)")
    missing = [t for t in loc.banner_must_contain if t.lower() not in b]
    if missing:
        raise StoreMismatch(f"banner '{banner}' is missing expected tokens {missing}")
    if loc.store_id and cookie_blob and loc.store_id not in cookie_blob:
        raise StoreMismatch(f"store_id {loc.store_id} not present in store cookie")
    return True
