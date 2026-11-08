#!/usr/bin/env python3
"""aqi-ops MCP server: Delhi-NCR Indian AQI, forecasts, farm fires and smoke outlook from open data.

Runs over stdio. Relative paths resolve against AQIOPS_PROJECT_DIR, else CLAUDE_PROJECT_DIR, else cwd.
Keys (all optional, all free): FIRMS_MAP_KEY (NASA FIRMS fires), DATA_GOV_IN_KEY (CPCB stations),
TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (alerts).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as FastMCP  # noqa: E402
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP  # noqa: E402

from aqiops import __version__, aqi as A, cpcb, fires as F, http, locations as L, openmeteo as OM  # noqa: E402

mcp = FastMCP("aqi-ops")

FALLBACK = ("The MCP server could not reach the API (sandbox allowlist or no internet). Fetch `url` with "
            "WebFetch, asking for the raw JSON, then pass that text to analyze_open_meteo_json.")


def _base() -> Path:
    return Path(os.environ.get("AQIOPS_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def _fail(e: Exception, extra: dict | None = None) -> dict:
    out = {"ok": False, "error": str(e)}
    if isinstance(e, http.FetchError):
        out["url"] = e.url
    return {**out, **(extra or {})}


def _points(places: str | None) -> list[dict]:
    return L.resolve(places)


@mcp.tool()
def aqi_status() -> dict:
    """Report plugin version, which optional keys are set, whether Open-Meteo is reachable, and whether
    the current project looks like the ncr-aqi-tracker dashboard. Call first when unsure."""
    try:
        http.get(OM.aq_url(L.LOCATIONS[:1], forecast_days=1, past_days=0), timeout=10)
        reach = True
    except Exception as e:  # noqa: BLE001
        reach = f"no ({e})"
    base = _base()
    return {
        "version": __version__, "project_dir": str(base),
        "open_meteo_reachable": reach,
        "keys": {"FIRMS_MAP_KEY": bool(F.get_key()), "DATA_GOV_IN_KEY": bool(cpcb.get_key()),
                 "TELEGRAM": bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))},
        "dashboard_found": (base / "index.html").exists() and (base / "fetch_fires.py").exists(),
        "locations": [l["name"] for l in L.LOCATIONS],
    }


@mcp.tool()
def current_aqi(places: str = "all", mode: str = "pm", include_wind: bool = True) -> dict:
    """Current Indian (CPCB) AQI for Delhi-NCR places, sorted worst first.

    places: 'all' (12 NCR points), a known name/alias ('Noida', 'Gurgaon', 'Anand Vihar'), 'lat,lon', any
    Indian place name (geocoded), or several separated by ';'.
    mode: 'pm' = PM2.5/PM10 only, same as the dashboard; 'all' = also NO2, SO2, CO (8-h), O3 (8-h).
    The AQI uses trailing 24-h (8-h for CO/O3) means of modelled concentrations."""
    if mode not in OM.MODES:
        return {"ok": False, "error": "mode must be 'pm' or 'all'"}
    try:
        pts = _points(places)
        raw = OM.fetch_aq(pts)
    except Exception as e:  # noqa: BLE001
        return _fail(e, {"fallback": FALLBACK} if isinstance(e, http.FetchError) else None)
    rows = sorted((OM.current(r, p, mode) for r, p in zip(raw, pts)), key=lambda x: -(x["aqi"] or -1))
    out = {"ok": True, "mode": mode, "results": rows, "caveat": OM.CAVEAT}
    if include_wind:
        try:
            w = OM.wind_summary(OM.fetch_wx())
            w.pop("daily", None)
            out["delhi_wind"] = w
        except Exception as e:  # noqa: BLE001
            out["delhi_wind"] = {"error": str(e)}
    return out


@mcp.tool()
def aqi_forecast(place: str = "Connaught Place, Delhi", days: int = 4, mode: str = "pm",
                 hourly_step: int = 0) -> dict:
    """Day-by-day AQI outlook (IST) for one place: daily AQI from each day's 24-h mean, plus the peak
    rolling AQI and when it peaks. days 1-5. hourly_step > 0 adds a rolling AQI series every N hours.
    Also returns daily Delhi wind, share of north-westerly hours and minimum mixing-layer height."""
    days = max(1, min(5, int(days)))
    try:
        pt = _points(place)[0]
        r = OM.fetch_aq([pt], forecast_days=days)[0]
    except Exception as e:  # noqa: BLE001
        return _fail(e, {"fallback": FALLBACK} if isinstance(e, http.FetchError) else None)
    out = {"ok": True, **OM.forecast(r, pt, mode), "caveat": OM.CAVEAT}
    if hourly_step:
        out["rolling"] = OM.hourly_rolling(r, mode, max(1, int(hourly_step)))
    try:
        out["delhi_weather"] = OM.wind_summary(OM.fetch_wx(forecast_days=days)).get("daily")
    except Exception as e:  # noqa: BLE001
        out["delhi_weather"] = {"error": str(e)}
    return out


@mcp.tool()
def compute_aqi(pm25: float | None = None, pm10: float | None = None, no2: float | None = None,
                so2: float | None = None, co_mg: float | None = None, o3: float | None = None) -> dict:
    """Offline CPCB AQI calculator from averaged concentrations (ug/m3; CO in mg/m3). Use 24-h means for
    PM2.5, PM10, NO2, SO2 and 8-h means for CO and O3."""
    return A.compute({"pm25": pm25, "pm10": pm10, "no2": no2, "so2": so2, "co": co_mg, "o3": o3})


@mcp.tool()
def analyze_open_meteo_json(json_text: str, places: str = "all", mode: str = "pm", days: int = 0) -> dict:
    """Compute AQI from raw Open-Meteo air-quality JSON fetched some other way (e.g. WebFetch when the
    server has no network). places must list the same points, in the same order, as the request URL.
    days > 0 also returns the daily forecast."""
    try:
        data = json.loads(json_text)
        data = data if isinstance(data, list) else [data]
        pts = _points(places)
        if len(pts) != len(data):
            return {"ok": False, "error": f"{len(data)} JSON objects but {len(pts)} places"}
        res = []
        for r, p in zip(data, pts):
            row = OM.current(r, p, mode)
            if days:
                row["forecast"] = OM.forecast(r, p, mode)["days"][:days]
            res.append(row)
        return {"ok": True, "results": sorted(res, key=lambda x: -(x["aqi"] or -1)), "caveat": OM.CAVEAT}
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@mcp.tool()
def request_urls(places: str = "all", forecast_days: int = 4, compact: bool = True) -> dict:
    """Return the Open-Meteo URLs (air quality + Delhi weather) for the places, for use with WebFetch when
    the server cannot reach the network. compact=True (default) requests PM2.5/PM10 only, which keeps the
    URL short; analyze its JSON with mode 'pm'."""
    try:
        pts = _points(places)
    except Exception as e:  # noqa: BLE001
        return _fail(e)
    return {"air_quality": OM.aq_url(pts, forecast_days, compact=compact), "weather": OM.wx_url(forecast_days=forecast_days),
            "places_in_order": [p["name"] for p in pts]}


@mcp.tool()
def fire_activity(days: int = 2, source: str = "VIIRS_SNPP_NRT", key: str | None = None) -> dict:
    """NASA FIRMS active fires (farm/stubble fires) over Punjab, Haryana and NCR for the last 1-10 days:
    counts, fire radiative power (MW) by date and rough region, how much lies upwind (NW) of Delhi, and the
    strongest detections. Low-confidence detections are dropped. Needs FIRMS_MAP_KEY."""
    k = F.get_key(key)
    if not k:
        return {"ok": False, "error": F.KEY_HELP}
    try:
        fl = F.fetch(k, source, days)
    except Exception as e:  # noqa: BLE001
        return _fail(e)
    return {"ok": True, "source": source, "days": days, "bbox": F.BBOX, **F.summarize(fl)}


@mcp.tool()
def smoke_outlook(days: int = 2, forecast_days: int = 4, source: str = "VIIRS_SNPP_NRT") -> dict:
    """Stubble-smoke transport outlook for Delhi-NCR: combines recent upwind fire power (FIRMS, if a key is
    set) with forecast north-westerly wind share, wind speed and mixing-layer depth. A heuristic, not a
    source attribution."""
    try:
        wind = OM.wind_summary(OM.fetch_wx(forecast_days=max(1, min(5, forecast_days))))
    except Exception as e:  # noqa: BLE001
        return _fail(e)
    summ, warn = None, None
    k = F.get_key()
    if k:
        try:
            summ = F.summarize(F.fetch(k, source, days))
        except Exception as e:  # noqa: BLE001
            warn = f"fires unavailable: {e}"
    else:
        warn = "No FIRMS_MAP_KEY: outlook uses weather only. " + F.KEY_HELP
    out = {"ok": True, "current_wind": {k2: v for k2, v in wind.items() if k2 != "daily"},
           **F.smoke_outlook(summ, wind)}
    if summ:
        out["fires"] = {k2: summ[k2] for k2 in ("count", "total_frp_mw", "upwind_nw_of_delhi")}
    if warn:
        out["warning"] = warn
    return out


@mcp.tool()
def refresh_fires_json(days: int = 2, source: str = "VIIRS_SNPP_NRT", out: str = "data/fires.json") -> dict:
    """Fetch FIRMS fires and write the dashboard's data/fires.json (same schema as fetch_fires.py).
    `out` is relative to the project directory. Needs FIRMS_MAP_KEY."""
    k = F.get_key()
    if not k:
        return {"ok": False, "error": F.KEY_HELP}
    try:
        fl = F.fetch(k, source, days)
    except Exception as e:  # noqa: BLE001
        return _fail(e)
    p = Path(out)
    p = p if p.is_absolute() else _base() / p
    return {"ok": True, **F.write_fires_json(fl, p, source, days)}


@mcp.tool()
def forecast_alerts(threshold: int = 300, places: str = "all", forecast_days: int = 4,
                    send_telegram: bool = False) -> dict:
    """Find places whose forecast rolling AQI crosses `threshold` (default 300 = 'Very Poor' and above),
    with the first crossing time and the peak. send_telegram=True posts a summary when TELEGRAM_BOT_TOKEN
    and TELEGRAM_CHAT_ID are set; only do that when the user asked for it."""
    try:
        pts = _points(places)
        raw = OM.fetch_aq(pts, forecast_days=max(1, min(5, forecast_days)))
    except Exception as e:  # noqa: BLE001
        return _fail(e)
    hits = []
    for r, p in zip(raw, pts):
        series = OM.hourly_rolling(r, "pm", 1)
        over = [s for s in series if (s["aqi"] or 0) > threshold]
        if over:
            peak = max(series, key=lambda s: s["aqi"] or 0)
            hits.append({"place": p["name"], "first_over_ist": over[0]["time_ist"], "hours_over": len(over),
                         "peak_aqi": peak["aqi"], "peak_at_ist": peak["time_ist"], "peak_category": peak["category"]})
    out = {"ok": True, "threshold": threshold, "alerts": hits, "caveat": OM.CAVEAT}
    if send_telegram:
        tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not (tok and chat):
            out["telegram"] = "not sent: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
        elif not hits:
            out["telegram"] = "not sent: nothing above threshold"
        else:
            lines = [f"NCR AQI forecast above {threshold}:"] + [
                f"- {h['place']}: peak {h['peak_aqi']} ({h['peak_category']}) at {h['peak_at_ist']} IST" for h in hits]
            text = "\n".join(lines) + "\n(CAMS model estimate)"
            q = urllib.parse.urlencode({"chat_id": chat, "text": text})
            try:
                http.get(f"https://api.telegram.org/bot{tok}/sendMessage?{q}", timeout=20)
                out["telegram"] = "sent"
            except Exception as e:  # noqa: BLE001
                out["telegram"] = f"failed: {str(e).replace(tok, '***')}"
    return out


@mcp.tool()
def cpcb_compare(place: str = "Anand Vihar, Delhi", k: int = 3) -> dict:
    """Compare the CAMS model estimate at a place with the k nearest CPCB ground stations (data.gov.in
    real-time feed). Needs DATA_GOV_IN_KEY. Station values are passed through as published."""
    key = cpcb.get_key()
    if not key:
        return {"ok": False, "error": cpcb.KEY_HELP}
    try:
        pt = _points(place)[0]
        model = OM.current(OM.fetch_aq([pt])[0], pt, "pm")
        st = cpcb.nearest(cpcb.ncr_stations(key), pt["lat"], pt["lon"], k)
    except Exception as e:  # noqa: BLE001
        return _fail(e)
    return {"ok": True, "model": {"place": pt["name"], "aqi": model["aqi"], "averages_24h": model["averages"]},
            "stations": st,
            "note": "Model is a ~10-40 km grid average; stations are point readings, often near roads. "
                    "Expect the model to under-read hotspots like Anand Vihar."}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
