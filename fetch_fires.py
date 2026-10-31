#!/usr/bin/env python3
"""Fetch active-fire (farm-fire) detections over Punjab, Haryana and NCR from NASA FIRMS.

Writes data/fires.json, which index.html shows when "Show farm fires" is ticked.

Get a free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/
Usage:
    python fetch_fires.py --key YOUR_MAP_KEY            # last 2 days, VIIRS S-NPP
    python fetch_fires.py --days 5 --source VIIRS_NOAA20_NRT
    FIRMS_MAP_KEY=... python fetch_fires.py
"""
import argparse
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# west, south, east, north — covers Punjab, Haryana, Delhi-NCR and western UP
BBOX = (73.8, 27.5, 78.5, 32.5)
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}"


def fetch(key: str, source: str, days: int) -> list[dict]:
    url = API.format(key=key, source=source, bbox=",".join(map(str, BBOX)), days=days)
    with urllib.request.urlopen(url, timeout=60) as r:
        text = r.read().decode("utf-8")
    if not text.startswith("latitude"):
        raise RuntimeError(f"Unexpected FIRMS response: {text[:200]}")
    fires = []
    for row in csv.DictReader(io.StringIO(text)):
        conf = row.get("confidence", "")
        if conf in ("l", "low"):          # drop low-confidence detections
            continue
        t = row["acq_time"].zfill(4)
        fires.append({
            "lat": float(row["latitude"]),
            "lon": float(row["longitude"]),
            "date": row["acq_date"],
            "time": f"{t[:2]}:{t[2:]} UTC",
            "frp": float(row.get("frp") or 0),   # fire radiative power, MW
            "confidence": conf,
        })
    return fires


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--key", default="218b79c71e1c58514c79fd54d6866794", help="FIRMS MAP_KEY (or set FIRMS_MAP_KEY)")
#    p.add_argument("--key", default=os.environ.get("FIRMS_MAP_KEY"), help="FIRMS MAP_KEY (or set FIRMS_MAP_KEY)")
    p.add_argument("--days", type=int, default=2, choices=range(1, 11), metavar="1-10")
    p.add_argument("--source", default="VIIRS_SNPP_NRT",
                   help="VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT or MODIS_NRT")
    p.add_argument("--out", default=str(Path(__file__).parent / "data" / "fires.json"))
    a = p.parse_args()
    if not a.key:
        p.error("a FIRMS MAP_KEY is required (--key or FIRMS_MAP_KEY)")

    fires = fetch(a.key, a.source, a.days)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source": a.source,
        "days": a.days,
        "bbox": BBOX,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "fires": fires,
    }, indent=1))
    print(f"Wrote {len(fires)} fire detections to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
