---
name: air-quality-report
description: "This skill should be used when the user asks \"what's the AQI in Noida\", \"how bad is the air in Delhi today\", \"is tomorrow better\", \"AQI forecast for Gurugram\", \"which part of NCR is cleanest\", \"should I go for a run\", \"is it safe to go out\", or runs /air-quality-report. Gives the Indian (CPCB) AQI, main pollutant, trend and forecast for Delhi-NCR places from the CAMS model via Open-Meteo."
metadata:
  version: "0.1.0"
---

# Air-quality report (Delhi-NCR)

Answer in the reply: a short, numbers-first report. Never estimate AQI values in prose - every number
comes from an aqi-ops tool.

## Procedure

1. **Resolve the place.** Pass the user's words to the tool's `places`/`place` argument: known names and
   aliases (Noida, Gurgaon, Anand Vihar, Greater Noida...), `lat,lon`, or any Indian place name (geocoded).
   Several places: separate with `;`. Whole region: `all`.
2. **Fetch.**
   - Now / today: `current_aqi` (mode `pm` by default; use `all` if the user asks about NO2, ozone, CO or
     traffic pollution).
   - Tomorrow / this week / "when will it improve": `aqi_forecast` (days 2-5). For "what time is worst",
     add `hourly_step: 3`.
   - Comparing places: `current_aqi` with `places: "all"` or a `;` list; results come back worst first.
3. **If a tool returns `ok: false` with a `url`** (the server can't reach the internet): call `request_urls`
   if needed, fetch the air-quality URL with WebFetch asking for the raw JSON, then pass it to
   `analyze_open_meteo_json` with the same `places` in the same order. Say once that the data came via the
   fallback.
4. **Write the answer:**
   - One line per place: AQI, category, driver pollutant (e.g. "Noida Sec 62 - 312, Very Poor, PM2.5").
   - Trend: forecast direction over the next days, and the worst hour if fetched.
   - Wind: if `delhi_wind.north_westerly` is true in Oct-Nov, mention that NW winds bring Punjab/Haryana
     stubble smoke; offer the `stubble-smoke` analysis when fires look relevant.
   - One practical line keyed to the category (use `category.health`): N95 outdoors from Very Poor up; move
     exercise indoors or to the cleanest hour when Poor or worse; air purifier with windows shut when Severe.
   - The caveat, once: a model estimate (CAMS ~10-40 km grid), not an official CPCB station reading;
     hotspots like Anand Vihar usually read higher on the ground. If they want official numbers, offer
     `cpcb_compare` (needs DATA_GOV_IN_KEY) or point them to the CPCB / SAMEER app.
5. **Sources line:** Open-Meteo Air Quality API (Copernicus CAMS); add NASA FIRMS if fires were used.

## Reference

| AQI | Category | PM2.5 24-h (ug/m3) | PM10 24-h (ug/m3) |
|---|---|---|---|
| 0-50 | Good | 0-30 | 0-50 |
| 51-100 | Satisfactory | 31-60 | 51-100 |
| 101-200 | Moderate | 61-90 | 101-250 |
| 201-300 | Poor | 91-120 | 251-350 |
| 301-400 | Very Poor | 121-250 | 351-430 |
| 401-500 | Severe | 250+ | 430+ |

The AQI is the highest pollutant sub-index. `compute_aqi` does this offline for numbers the user gives you.
