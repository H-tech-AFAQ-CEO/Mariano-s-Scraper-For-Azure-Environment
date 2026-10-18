"""Exceptions, structured logging and retry helper."""
import datetime as dt
import json
import logging
import random
import sys
import time


class ScraperError(Exception):
    pass


class TransientError(ScraperError):
    """Network/timeouts/5xx - safe to retry."""


class BlockedError(ScraperError):
    """Bot challenge / 403 / 429 / interstitial detected."""


class ShapeError(ScraperError):
    """200 response whose content is not a recognisable page (silent block / site change)."""


class StoreMismatch(ScraperError):
    """The page is not showing the configured store."""


class LockHeld(ScraperError):
    pass


class ValidationFailed(ScraperError):
    pass


class JsonFormatter(logging.Formatter):
    def format(self, r):
        d = {
            "ts": dt.datetime.fromtimestamp(r.created, dt.timezone.utc).isoformat(timespec="seconds"),
            "level": r.levelname,
            "event": r.getMessage(),
        }
        d.update(getattr(r, "fields", {}))
        if r.exc_info:
            d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, default=str, ensure_ascii=False)


def get_logger(name="marianos", log_file=None):
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    log.addHandler(h)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        log.addHandler(fh)
    log.propagate = False
    return log


def ev(log, event, level="info", **fields):
    log.log(getattr(logging, level.upper()), event, extra={"fields": fields})


def with_retries(fn, attempts, base_delay, log, what, sleep=time.sleep, **ctx):
    """Retry only TransientError with exponential backoff + jitter."""
    for i in range(1, attempts + 1):
        try:
            return fn()
        except TransientError as e:
            if i == attempts:
                ev(log, "retry_exhausted", level="error", what=what, attempts=attempts, error=str(e), **ctx)
                raise
            delay = base_delay * 2 ** (i - 1) + random.uniform(0, base_delay)
            ev(log, "retry", level="warning", what=what, attempt=i, delay_s=round(delay, 1), error=str(e), **ctx)
            sleep(delay)


def utcnow():
    return dt.datetime.now(dt.timezone.utc)
