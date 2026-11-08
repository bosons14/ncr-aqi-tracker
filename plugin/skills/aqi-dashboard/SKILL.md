---
name: aqi-dashboard
description: "This skill should be used when the user asks to \"run the AQI dashboard\", \"add a location to the tracker\", \"add a new data layer\", \"add Sentinel-5P NO2\", \"compare with CPCB stations\", \"set up AQI alerts\", \"deploy the tracker to GitHub Pages\", or otherwise change or extend the ncr-aqi-tracker project (index.html, fetch_fires.py, data/), or runs /aqi-dashboard."
metadata:
  version: "0.1.0"
---

# NCR AQI tracker dashboard

Work in the user's `ncr-aqi-tracker` checkout (github.com/bosons14/ncr-aqi-tracker). Read its `CLAUDE.md`
first and follow it; the rules below repeat the essentials.

## Ground rules

- `index.html` is one self-contained page: no build step, no framework, Leaflet 1.9.4 and Chart.js 4.4.1
  from cdnjs, all logic inline. Keep it runnable with `python -m http.server 8000`.
- Python is stdlib only unless a feature truly needs more (e.g. `openeo` for Sentinel-5P); then add
  `requirements.txt`.
- New data layer = a fetcher script writing `data/<layer>.json` + a header toggle, following the fire layer
  (`fetch_fires.py` -> `data/fires.json` -> `toggleFires`).
- IST everywhere (`timezone=Asia/Kolkata`); FIRMS times stay UTC and are labelled so.
- `BP`/`CATS` in index.html must match CPCB and this plugin's `aqiops/aqi.py`; the plugin's hook warns if
  an edit makes them diverge. Keep `LOCATIONS` in step with `aqiops/locations.py` if you add places and
  want the tools to know them.
- Never commit API keys. Keys come from env vars (`FIRMS_MAP_KEY`, `DATA_GOV_IN_KEY`, `TELEGRAM_*`) or,
  for the browser-only `CARTO_KEY`, a value the user chooses to set.

## Common tasks

- **Run it:** `python3 fetch_fires.py` (optional, needs FIRMS key) then `python3 -m http.server 8000` and
  open http://localhost:8000. Or call `refresh_fires_json` instead of the script.
- **Add a location:** append `{name, lat, lon}` to `LOCATIONS` (Open-Meteo takes comma-separated
  coordinates, so no other change is needed).
- **CPCB ground truth (roadmap 3):** a `fetch_cpcb.py` writing `data/cpcb.json` from the data.gov.in feed
  (see `aqiops/cpcb.py` for the resource id and field handling) and station markers on the map.
- **Alerts (roadmap 4):** `forecast_alerts` with `send_telegram: true` posts to Telegram; for a schedule,
  a GitHub Action or cron that runs a small script using the same logic.
- **Sentinel-5P NO2 (roadmap 1):** Copernicus Data Space via openEO or STAC; render as a Leaflet image
  overlay with its own toggle and a colour scale legend.
- **Deploy (roadmap 6):** GitHub Pages for the page, plus `.github/workflows/fires.yml` on a cron (e.g.
  every 3 h) that runs `fetch_fires.py` with `FIRMS_MAP_KEY` from repository secrets and commits
  `data/fires.json`.

## Testing

The sandbox usually can't reach Open-Meteo, cdnjs or tile servers. Install `leaflet` and `chart.js` from npm,
use Playwright `page.route` to serve them locally and to mock Open-Meteo with the JSON shape described in
`CLAUDE.md`, screenshot the page and check the console has no errors. Run `python3 -m unittest discover -s
plugin/tests` for the plugin. Say clearly that live data was not tested if it wasn't.
