"""CPCB National Air Quality Index (India).

Breakpoints follow the CPCB National AQI (2014). The PM tables must stay identical to `BP` in the
dashboard's index.html; the plugin's hook checks this whenever index.html is edited.

Averaging periods per CPCB: PM2.5, PM10, NO2, SO2, NH3 use 24-h means; CO and O3 use 8-h means.
CO breakpoints are in mg/m3 (Open-Meteo returns ug/m3, so divide by 1000). Everything else is ug/m3.
"""

from __future__ import annotations

# (conc_low, conc_high, index_low, index_high)
BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200), (90, 120, 201, 300),
             (120, 250, 301, 400), (250, 380, 401, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200), (250, 350, 201, 300),
             (350, 430, 301, 400), (430, 510, 401, 500)],
    "no2": [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200), (180, 280, 201, 300),
            (280, 400, 301, 400), (400, 500, 401, 500)],
    "so2": [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200), (380, 800, 201, 300),
            (800, 1600, 301, 400), (1600, 2000, 401, 500)],
    "co": [(0, 1.0, 0, 50), (1.0, 2.0, 51, 100), (2.0, 10, 101, 200), (10, 17, 201, 300),
           (17, 34, 301, 400), (34, 50, 401, 500)],
    "o3": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200), (168, 208, 201, 300),
           (208, 748, 301, 400), (748, 1000, 401, 500)],
}

AVERAGING_HOURS = {"pm25": 24, "pm10": 24, "no2": 24, "so2": 24, "co": 8, "o3": 8}

# Open-Meteo variable name, and the factor that converts its unit to the CPCB unit.
OPEN_METEO_VARS = {
    "pm25": ("pm2_5", 1.0), "pm10": ("pm10", 1.0), "no2": ("nitrogen_dioxide", 1.0),
    "so2": ("sulphur_dioxide", 1.0), "co": ("carbon_monoxide", 0.001), "o3": ("ozone", 1.0),
}

LABELS = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO2", "so2": "SO2", "co": "CO", "o3": "O3"}

CATEGORIES = [
    (50, "Good", "#4caf50", "Minimal impact."),
    (100, "Satisfactory", "#a3d65c", "Minor breathing discomfort for sensitive people."),
    (200, "Moderate", "#ffd54f", "Breathing discomfort for people with lung or heart disease, children and older adults."),
    (300, "Poor", "#ff9800", "Breathing discomfort for most people on prolonged exposure."),
    (400, "Very Poor", "#f44336", "Respiratory illness on prolonged exposure; wear an N95 outdoors."),
    (500, "Severe", "#a0153e", "Affects healthy people; serious for those with existing disease. Avoid outdoor exertion."),
]


def sub_index(conc: float | None, pollutant: str) -> int | None:
    """Linear interpolation inside the CPCB band. Values above the top band cap at 500."""
    if conc is None or conc != conc or conc < 0:
        return None
    for cl, ch, il, ih in BREAKPOINTS[pollutant]:
        if conc <= ch:
            return round(il + (ih - il) * (conc - cl) / (ch - cl))
    return 500


def category(aqi: int | None) -> dict | None:
    if aqi is None:
        return None
    for top, name, color, note in CATEGORIES:
        if aqi <= top:
            return {"name": name, "color": color, "health": note}
    top, name, color, note = CATEGORIES[-1]
    return {"name": name, "color": color, "health": note}


def compute(concs: dict[str, float | None]) -> dict:
    """AQI from averaged concentrations (keys: pm25, pm10, no2, so2, co[mg/m3], o3).

    Returns the overall AQI (max sub-index), the driving pollutant, all sub-indices and the category.
    """
    subs = {p: sub_index(concs.get(p), p) for p in BREAKPOINTS if concs.get(p) is not None}
    subs = {p: s for p, s in subs.items() if s is not None}
    if not subs:
        return {"aqi": None, "driver": None, "sub_indices": {}, "category": None}
    driver = max(subs, key=lambda p: subs[p])
    aqi = subs[driver]
    out = {"aqi": aqi, "driver": LABELS[driver], "sub_indices": {LABELS[p]: s for p, s in subs.items()},
           "category": category(aqi)}
    if not any(p in subs for p in ("pm25", "pm10")):
        out["note"] = "CPCB requires PM2.5 or PM10 among the pollutants; this AQI is indicative only."
    return out


def mean(values) -> float | None:
    v = [x for x in values if x is not None]
    return sum(v) / len(v) if v else None
