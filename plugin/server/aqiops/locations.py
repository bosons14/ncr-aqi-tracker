"""NCR monitoring points (same list as LOCATIONS in index.html) and place lookup."""

from __future__ import annotations

import json
import math
import urllib.parse

from . import http

LOCATIONS = [
    {"name": "Connaught Place, Delhi", "lat": 28.6315, "lon": 77.2167},
    {"name": "Anand Vihar, Delhi", "lat": 28.6469, "lon": 77.3159},
    {"name": "Rohini, Delhi", "lat": 28.7360, "lon": 77.1130},
    {"name": "Dwarka, Delhi", "lat": 28.5921, "lon": 77.0460},
    {"name": "Okhla, Delhi", "lat": 28.5355, "lon": 77.2710},
    {"name": "Noida Sector 62", "lat": 28.6270, "lon": 77.3720},
    {"name": "Noida Sector 125", "lat": 28.5440, "lon": 77.3290},
    {"name": "Greater Noida", "lat": 28.4744, "lon": 77.5040},
    {"name": "Ghaziabad", "lat": 28.6692, "lon": 77.4538},
    {"name": "Gurugram", "lat": 28.4595, "lon": 77.0266},
    {"name": "Faridabad", "lat": 28.4089, "lon": 77.3178},
    {"name": "Sonipat", "lat": 28.9931, "lon": 77.0151},
]

ALIASES = {
    "delhi": "Connaught Place, Delhi", "new delhi": "Connaught Place, Delhi", "cp": "Connaught Place, Delhi",
    "noida": "Noida Sector 62", "gurgaon": "Gurugram", "ggn": "Gurugram", "gzb": "Ghaziabad",
    "greno": "Greater Noida", "gr noida": "Greater Noida", "anand vihar": "Anand Vihar, Delhi",
}

DELHI = (28.6139, 77.2090)
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def bearing_deg(frm: tuple[float, float], to: tuple[float, float]) -> float:
    """Initial bearing from `frm` to `to`, degrees clockwise from north."""
    la1, lo1, la2, lo2 = map(math.radians, (*frm, *to))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _norm(s: str) -> str:
    return " ".join(s.lower().replace(",", " ").replace("-", " ").split())


def resolve(place: str | None) -> list[dict]:
    """Turn a user place string into points. Empty / 'all' / 'ncr' -> all 12 locations.

    Accepts a known location name or alias, 'lat,lon', or any other place name (geocoded via Open-Meteo,
    restricted to India). Raises ValueError if nothing matches.
    """
    if not place or _norm(place) in ("all", "ncr", "delhi ncr", "delhi ncr all"):
        return [dict(l) for l in LOCATIONS]
    out = []
    for part in [p for p in place.split(";") if p.strip()] if ";" in place else [place]:
        out.append(_resolve_one(part.strip()))
    return out


def _resolve_one(place: str) -> dict:
    parts = place.replace(" ", "").split(",")
    if len(parts) == 2:
        try:
            lat, lon = float(parts[0]), float(parts[1])
            return {"name": f"{lat:.4f},{lon:.4f}", "lat": lat, "lon": lon}
        except ValueError:
            pass
    n = _norm(place)
    if n in ALIASES:
        return next(dict(l) for l in LOCATIONS if l["name"] == ALIASES[n])
    for l in LOCATIONS:
        if n == _norm(l["name"]) or n in _norm(l["name"]):
            return dict(l)
    q = urllib.parse.urlencode({"name": place, "count": 5, "language": "en", "format": "json", "countryCode": "IN"})
    data = json.loads(http.get(f"{GEOCODE_URL}?{q}"))
    hits = data.get("results") or []
    if not hits:
        raise ValueError(f"Could not find '{place}'. Give a known NCR location or 'lat,lon'.")
    h = min(hits, key=lambda r: haversine_km(DELHI, (r["latitude"], r["longitude"])))  # prefer the NCR match
    name = ", ".join(x for x in (h.get("name"), h.get("admin2") or h.get("admin1")) if x)
    return {"name": name, "lat": h["latitude"], "lon": h["longitude"], "geocoded": True}
