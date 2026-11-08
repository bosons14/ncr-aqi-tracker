"""Open-Meteo Air Quality (Copernicus CAMS) and Forecast clients, plus AQI processing.

Open-Meteo accepts comma-separated latitude/longitude and returns a JSON array, one object per point.
All times are requested in IST (timezone=Asia/Kolkata).
"""

from __future__ import annotations

import json
import urllib.parse
from collections import OrderedDict

from . import aqi as A
from . import http

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WX_URL = "https://api.open-meteo.com/v1/forecast"
TZ = "Asia/Kolkata"

AQ_VARS = ["pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone",
           "aerosol_optical_depth", "dust"]
MODES = {"pm": ("pm25", "pm10"), "all": ("pm25", "pm10", "no2", "so2", "co", "o3")}
CAVEAT = ("Estimate from the Copernicus CAMS model via Open-Meteo (~10-40 km grid), not an official CPCB "
          "station reading.")


def aq_url(points: list[dict], forecast_days: int = 4, past_days: int = 1, compact: bool = False) -> str:
    """compact=True asks only for PM2.5/PM10 (enough for mode 'pm') and keeps the URL short for WebFetch."""
    vars_ = ["pm2_5", "pm10"] if compact else AQ_VARS
    q = {
        "latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points),
        "timezone": TZ, "past_days": past_days, "forecast_days": forecast_days,
        "current": ",".join(vars_ if compact else ["us_aqi"] + vars_), "hourly": ",".join(vars_),
    }
    return f"{AQ_URL}?{urllib.parse.urlencode(q, safe=',/')}"


def wx_url(lat: float = 28.6139, lon: float = 77.2090, forecast_days: int = 4) -> str:
    q = {
        "latitude": lat, "longitude": lon, "timezone": TZ, "forecast_days": forecast_days,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
        "hourly": "wind_speed_10m,wind_direction_10m,boundary_layer_height,relative_humidity_2m",
    }
    return f"{WX_URL}?{urllib.parse.urlencode(q)}"


def fetch_aq(points: list[dict], forecast_days: int = 4) -> list[dict]:
    data = json.loads(http.get(aq_url(points, forecast_days)))
    return data if isinstance(data, list) else [data]


def fetch_wx(lat: float = 28.6139, lon: float = 77.2090, forecast_days: int = 4) -> dict:
    return json.loads(http.get(wx_url(lat, lon, forecast_days)))


# ---------- processing ----------

def _now_index(r: dict) -> int:
    t = r["hourly"]["time"]
    cur = r["current"]["time"][:13]
    return max(0, next((i for i, x in enumerate(t) if x >= cur), len(t) - 1))


def _series(h: dict, pollutant: str) -> list[float | None]:
    var, factor = A.OPEN_METEO_VARS[pollutant]
    return [None if x is None else x * factor for x in h.get(var) or []]


def _trailing(series: list, end: int, hours: int) -> float | None:
    return A.mean(series[max(0, end - hours + 1): end + 1])


def aqi_at(h: dict, idx: int, mode: str = "pm") -> dict:
    concs = {p: _trailing(_series(h, p), idx, A.AVERAGING_HOURS[p]) for p in MODES[mode]}
    out = A.compute(concs)
    out["averages"] = {A.LABELS[p]: None if v is None else round(v, 2 if p == "co" else 1) for p, v in concs.items()}
    return out


def current(r: dict, point: dict, mode: str = "pm") -> dict:
    """Current AQI from trailing CPCB averaging windows, plus the latest hourly readings."""
    idx = _now_index(r)
    res = aqi_at(r["hourly"], idx, mode)
    c = r.get("current", {})
    return {
        "place": point["name"], "lat": point["lat"], "lon": point["lon"], "as_of_ist": c.get("time"),
        **res,
        "now": {"PM2.5": c.get("pm2_5"), "PM10": c.get("pm10"), "NO2": c.get("nitrogen_dioxide"),
                "O3": c.get("ozone"), "CO_ug": c.get("carbon_monoxide"), "SO2": c.get("sulphur_dioxide"),
                "AOD": c.get("aerosol_optical_depth"), "dust": c.get("dust")},
        "us_aqi_model": c.get("us_aqi"),
    }


def forecast(r: dict, point: dict, mode: str = "pm") -> dict:
    """Day-by-day outlook in IST.

    daily_aqi: AQI from that calendar day's 24-h mean concentrations (like CPCB's daily figure).
    peak_rolling_aqi: highest trailing-window AQI reached during the day, and the hour it peaks.
    """
    h = r["hourly"]
    t = h["time"]
    now = _now_index(r)
    days: "OrderedDict[str, list[int]]" = OrderedDict()
    for i, ts in enumerate(t):
        days.setdefault(ts[:10], []).append(i)
    today = t[now][:10]
    out = []
    for day, idxs in days.items():
        if day < today:
            continue
        concs = {p: A.mean([_series(h, p)[i] for i in idxs]) for p in MODES[mode]}
        daily = A.compute(concs)
        rolling = [(aqi_at(h, i, mode)["aqi"], t[i]) for i in idxs if i >= now]
        peak = max((x for x in rolling if x[0] is not None), default=(None, None))
        out.append({
            "date": day, "partial_day": len(idxs) < 24 or day == today,
            "daily_aqi": daily["aqi"], "category": (daily["category"] or {}).get("name"), "driver": daily["driver"],
            "mean_pm25": None if concs.get("pm25") is None else round(concs["pm25"], 1),
            "mean_pm10": None if concs.get("pm10") is None else round(concs["pm10"], 1),
            "peak_rolling_aqi": peak[0], "peak_at_ist": peak[1],
        })
    return {"place": point["name"], "days": out}


def hourly_rolling(r: dict, mode: str = "pm", step: int = 3) -> list[dict]:
    """Rolling AQI every `step` hours from now to the end of the forecast (for charts and alerts)."""
    h, now = r["hourly"], _now_index(r)
    rows = []
    for i in range(now, len(h["time"]), step):
        a = aqi_at(h, i, mode)
        rows.append({"time_ist": h["time"][i], "aqi": a["aqi"], "category": (a["category"] or {}).get("name")})
    return rows


def wind_summary(wx: dict) -> dict:
    c = wx.get("current") or {}
    d = c.get("wind_direction_10m")
    out = {"as_of_ist": c.get("time"), "temperature_c": c.get("temperature_2m"),
           "humidity_pct": c.get("relative_humidity_2m"), "wind_kmh": c.get("wind_speed_10m"),
           "wind_from_deg": d, "wind_from": compass(d) if d is not None else None,
           "north_westerly": is_north_westerly(d)}
    h = wx.get("hourly") or {}
    if h.get("time"):
        days: "OrderedDict[str, list[int]]" = OrderedDict()
        for i, ts in enumerate(h["time"]):
            days.setdefault(ts[:10], []).append(i)
        out["daily"] = []
        for day, idxs in days.items():
            dirs = [h["wind_direction_10m"][i] for i in idxs if h["wind_direction_10m"][i] is not None]
            spd = A.mean([h["wind_speed_10m"][i] for i in idxs])
            blh = [h.get("boundary_layer_height", [None] * len(h["time"]))[i] for i in idxs]
            blh = [x for x in blh if x is not None]
            out["daily"].append({
                "date": day,
                "mean_wind_kmh": None if spd is None else round(spd, 1),
                "share_north_westerly": round(sum(is_north_westerly(x) for x in dirs) / len(dirs), 2) if dirs else None,
                "min_boundary_layer_m": min(blh) if blh else None,
            })
    return out


def is_north_westerly(deg: float | None) -> bool:
    """Wind FROM roughly 280-340 deg carries Punjab/Haryana smoke towards Delhi-NCR."""
    return deg is not None and 280 <= deg <= 340


def compass(deg: float) -> str:
    pts = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return pts[int((deg % 360) / 22.5 + 0.5) % 16]
