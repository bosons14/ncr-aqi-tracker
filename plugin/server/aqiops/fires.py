"""NASA FIRMS active fires over Punjab, Haryana and NCR, and a stubble-smoke outlook for Delhi-NCR.

Same bbox, filters and output schema as the dashboard's fetch_fires.py, so `write_fires_json` can
refresh data/fires.json for index.html.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import http
from .locations import DELHI, bearing_deg, haversine_km

BBOX = (73.8, 27.5, 78.5, 32.5)  # west, south, east, north
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}"
SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT")
KEY_HELP = ("A NASA FIRMS MAP_KEY is needed. Get one free at https://firms.modaps.eosdis.nasa.gov/api/map_key/ "
            "and set FIRMS_MAP_KEY in the environment (or pass key=...).")


def get_key(key: str | None = None) -> str | None:
    return key or os.environ.get("FIRMS_MAP_KEY") or None


def url(key: str, source: str = "VIIRS_SNPP_NRT", days: int = 2) -> str:
    return API.format(key=key, source=source, bbox=",".join(map(str, BBOX)), days=days)


def parse_csv(text: str) -> list[dict]:
    if not text.startswith("latitude"):
        raise RuntimeError(f"Unexpected FIRMS response: {text[:200]}")
    fires = []
    for row in csv.DictReader(io.StringIO(text)):
        conf = row.get("confidence", "")
        if conf in ("l", "low"):
            continue
        t = row["acq_time"].zfill(4)
        fires.append({
            "lat": float(row["latitude"]), "lon": float(row["longitude"]), "date": row["acq_date"],
            "time": f"{t[:2]}:{t[2:]} UTC", "frp": float(row.get("frp") or 0), "confidence": conf,
        })
    return fires


def fetch(key: str, source: str = "VIIRS_SNPP_NRT", days: int = 2) -> list[dict]:
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    if not 1 <= days <= 10:
        raise ValueError("days must be 1-10")
    return parse_csv(http.get(url(key, source, days), timeout=90))


def write_fires_json(fires: list[dict], out: Path, source: str, days: int) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": source, "days": days, "bbox": BBOX,
               "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "fires": fires}
    out.write_text(json.dumps(payload, indent=1))
    return {"path": str(out), "count": len(fires), "fetched_at": payload["fetched_at"]}


# Approximate Punjab-Haryana border as (lon, lat) points: Punjab lies north of this line.
_PB_HR = [(73.8, 29.95), (74.5, 29.85), (75.6, 29.95), (76.4, 30.2), (76.85, 30.55), (77.2, 31.0)]


def _interp(xs: list[tuple[float, float]], x: float) -> float:
    if x <= xs[0][0]:
        return xs[0][1]
    for (x0, y0), (x1, y1) in zip(xs, xs[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return xs[-1][1]


def region(lat: float, lon: float) -> str:
    """Rough region label from coordinates (no shapefiles): fine for a summary, wrong near borders."""
    if 28.4 <= lat <= 28.88 and 76.84 <= lon <= 77.35:
        return "Delhi (approx.)"
    if lon < 77.2 and lat > _interp(_PB_HR, lon):
        return "Punjab (approx.)"
    if lon < 74.6 and lat < 30.0:
        return "Rajasthan (approx.)"
    if lon <= 77.25 and lat >= 27.6:
        return "Haryana (approx.)"
    if lon > 77.2 and lat < 31.0:
        return "Western UP (approx.)"
    return "Other (approx.)"


def summarize(fires: list[dict]) -> dict:
    """Counts, FRP and where the fires sit relative to Delhi (upwind sector for NW winds)."""
    by_date: dict[str, dict] = {}
    by_region: dict[str, dict] = {}
    nw = {"count": 0, "frp_mw": 0.0}
    for f in fires:
        d = by_date.setdefault(f["date"], {"count": 0, "frp_mw": 0.0})
        d["count"] += 1
        d["frp_mw"] += f["frp"]
        g = by_region.setdefault(region(f["lat"], f["lon"]), {"count": 0, "frp_mw": 0.0})
        g["count"] += 1
        g["frp_mw"] += f["frp"]
        b = bearing_deg(DELHI, (f["lat"], f["lon"]))
        if 270 <= b <= 350 and haversine_km(DELHI, (f["lat"], f["lon"])) >= 50:
            nw["count"] += 1
            nw["frp_mw"] += f["frp"]
    rnd = lambda m: {k: {"count": v["count"], "frp_mw": round(v["frp_mw"], 1)} for k, v in sorted(m.items())}
    total_frp = sum(f["frp"] for f in fires)
    top = sorted(fires, key=lambda f: -f["frp"])[:5]
    return {
        "count": len(fires), "total_frp_mw": round(total_frp, 1),
        "by_date_utc": rnd(by_date), "by_region": rnd(by_region),
        "upwind_nw_of_delhi": {"count": nw["count"], "frp_mw": round(nw["frp_mw"], 1),
                               "share_of_frp": round(nw["frp_mw"] / total_frp, 2) if total_frp else None},
        "strongest": [{**f, "km_from_delhi": round(haversine_km(DELHI, (f["lat"], f["lon"]))),
                       "bearing_from_delhi": round(bearing_deg(DELHI, (f["lat"], f["lon"])))} for f in top],
    }


def smoke_outlook(fire_summary: dict | None, wind: dict) -> dict:
    """Qualitative transport outlook: upwind fire activity x north-westerly wind x shallow mixing layer.

    This is a heuristic, not an attribution. Real source apportionment needs back-trajectories (HYSPLIT)
    or a chemical transport model.
    """
    days = []
    upwind_frp = (fire_summary or {}).get("upwind_nw_of_delhi", {}).get("frp_mw") or 0
    for d in wind.get("daily") or []:
        nw = d.get("share_north_westerly") or 0
        blh = d.get("min_boundary_layer_m")
        calm = (d.get("mean_wind_kmh") or 99) < 8
        score = 0
        score += 2 if nw >= 0.5 else 1 if nw >= 0.25 else 0
        score += 2 if upwind_frp >= 500 else 1 if upwind_frp >= 100 else 0
        score += 1 if blh is not None and blh < 300 else 0
        score += 1 if calm else 0
        level = "high" if score >= 5 else "moderate" if score >= 3 else "low"
        reasons = []
        if nw >= 0.25:
            reasons.append(f"{int(nw * 100)}% of hours with NW wind")
        if upwind_frp:
            reasons.append(f"{upwind_frp:.0f} MW fire power upwind (NW)")
        if blh is not None and blh < 300:
            reasons.append(f"shallow mixing layer (min {blh:.0f} m)")
        if calm:
            reasons.append("calm winds trap local emissions")
        days.append({"date": d["date"], "smoke_transport_risk": level, "reasons": reasons})
    return {"days": days, "note": ("Heuristic outlook combining upwind fire power, wind direction and "
                                   "mixing-layer depth. Not a source attribution.")}
