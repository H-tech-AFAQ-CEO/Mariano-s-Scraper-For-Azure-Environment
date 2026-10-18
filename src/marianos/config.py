"""Configuration loading. Locations, categories and selectors are data, not code."""
import copy
import csv
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Location:
    id: str
    zipcode: str = ""
    store_id: str = ""
    store_details_url: str = ""
    store_name: str = ""
    store_location: str = ""
    store_logo: str = ""
    banner_must_contain: list = field(default_factory=list)
    canaries: list = field(default_factory=list)
    enabled: bool = True


@dataclass
class Category:
    name: str
    url: str
    scope: str = "Category + ALL subcategories"

    @property
    def kind(self):
        return "coupons" if "/savings/" in self.url and "coupon" in self.url.lower() else "listing"


@dataclass
class Config:
    settings: dict
    selectors: dict
    locations: dict
    categories: list
    config_dir: Path


def _deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(config_dir="config") -> Config:
    d = Path(config_dir)
    settings = yaml.safe_load((d / "settings.yaml").read_text(encoding="utf-8")) or {}
    selectors = yaml.safe_load((d / "selectors.yaml").read_text(encoding="utf-8")) or {}
    locs_raw = (yaml.safe_load((d / "locations.yaml").read_text(encoding="utf-8")) or {}).get("locations", [])
    locations = {}
    for l in locs_raw:
        loc = Location(**{k: v for k, v in l.items() if k in Location.__dataclass_fields__})
        if loc.id in locations:
            raise ValueError(f"duplicate location id {loc.id}")
        locations[loc.id] = loc
    cats = []
    with open(d / "categories.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("Category (Auto)") or row.get("Category") or "").strip()
            url = (row.get("URL") or "").strip()
            if name and url:
                cats.append(Category(name=name, url=url, scope=(row.get("Scope") or "").strip()))
    if not cats:
        raise ValueError("categories.csv has no usable rows")
    # environment overrides (never secrets in files)
    if os.getenv("MARIANOS_STORAGE"):
        settings.setdefault("storage", {})["backend"] = os.environ["MARIANOS_STORAGE"]
    return Config(settings=settings, selectors=selectors, locations=locations, categories=cats, config_dir=d)


def proxy_from_env():
    """Proxy settings come ONLY from the environment / Azure secrets."""
    server = os.getenv("PROXY_SERVER")
    if not server:
        return None
    p = {"server": server}
    if os.getenv("PROXY_USERNAME"):
        p["username"] = os.environ["PROXY_USERNAME"]
        p["password"] = os.getenv("PROXY_PASSWORD", "")
    return p
