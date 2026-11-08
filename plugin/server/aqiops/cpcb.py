"""CPCB real-time station data via the data.gov.in open API (ground truth for the CAMS model estimate).

Needs a free data.gov.in API key in DATA_GOV_IN_KEY (https://data.gov.in -> sign up -> My Account -> API key).
Resource: "Real time Air Quality Index from various locations". The feed has been seen with two field
spellings (min_value/max_value/avg_value and pollutant_min/pollutant_max/pollutant_avg); both are handled.
"""

from __future__ import annotations

import json
import os
import urllib.parse

from . import http
from .locations import haversine_km

RESOURCE = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
API = f"https://api.data.gov.in/resource/{RESOURCE}"
NCR_STATES = ("Delhi", "Haryana", "Uttar_Pradesh", "Uttar Pradesh")
NCR_CITIES = ("Delhi", "Noida", "Greater Noida", "Ghaziabad", "Gurugram", "Faridabad", "Sonipat")
KEY_HELP = "Set DATA_GOV_IN_KEY to a free data.gov.in API key to use CPCB station data."


def get_key(key: str | None = None) -> str | None:
    return key or os.environ.get("DATA_GOV_IN_KEY") or None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch(key: str, state: str | None = None, city: str | None = None, limit: int = 2000) -> list[dict]:
    q = {"api-key": key, "format": "json", "limit": limit}
    if state:
        q["filters[state]"] = state
    if city:
        q["filters[city]"] = city
    data = json.loads(http.get(f"{API}?{urllib.parse.urlencode(q)}", timeout=60))
    return data.get("records") or []


def stations(records: list[dict]) -> list[dict]:
    """Group the per-pollutant rows into one entry per station."""
    out: dict[str, dict] = {}
    for r in records:
        name = r.get("station")
        if not name:
            continue
        s = out.setdefault(name, {
            "station": name, "city": r.get("city"), "state": r.get("state"),
            "lat": _num(r.get("latitude")), "lon": _num(r.get("longitude")),
            "last_update": r.get("last_update"), "pollutants": {},
        })
        pid = (r.get("pollutant_id") or "").upper().replace("OZONE", "O3")
        s["pollutants"][pid] = {
            "avg": _num(r.get("avg_value", r.get("pollutant_avg"))),
            "min": _num(r.get("min_value", r.get("pollutant_min"))),
            "max": _num(r.get("max_value", r.get("pollutant_max"))),
        }
    return list(out.values())


def ncr_stations(key: str) -> list[dict]:
    recs = []
    for st in ("Delhi", "Haryana", "Uttar_Pradesh"):
        recs += fetch(key, state=st)
    return [s for s in stations(recs) if (s.get("city") or "") in NCR_CITIES or (s.get("state") == "Delhi")]


def nearest(stations_: list[dict], lat: float, lon: float, k: int = 3) -> list[dict]:
    have = [s for s in stations_ if s.get("lat") is not None and s.get("lon") is not None]
    for s in have:
        s["km"] = round(haversine_km((lat, lon), (s["lat"], s["lon"])), 1)
    return sorted(have, key=lambda s: s["km"])[:k]
