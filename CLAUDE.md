# CLAUDE.md — NCR Air Quality Tracker

## Layout
- `index.html` — self-contained dashboard (Leaflet + Chart.js from cdnjs). All logic is inline JS.
  - `LOCATIONS` — monitoring points; add or remove entries freely (Open-Meteo accepts comma-separated lat/lon).
  - `BP` / `CATS` — CPCB National AQI breakpoints and categories. Keep them in sync with CPCB if they change.
  - `fetchAll()` → `process()` → `render*()` — fetch, compute 24-h means/AQI, draw.
- `fetch_fires.py` — stdlib-only NASA FIRMS client; writes `data/fires.json` `{source, days, bbox, fetched_at, fires:[{lat,lon,date,time,frp,confidence}]}`.

## Conventions
- No build step and no framework; keep the page runnable by opening the file or serving it with `python -m http.server`.
- Python: stdlib only unless a feature truly needs more (e.g. openEO for Sentinel-5P). If so, put it in `requirements.txt`.
- New data layers: add a fetcher script that writes `data/<layer>.json` plus a toggle in the header, following the fire pattern.
- Times shown are in IST (`timezone=Asia/Kolkata`); FIRMS times are UTC and labelled as such.

## Testing
- Open in a browser and check the console. To test offline, stub `fetch` responses with the Open-Meteo JSON shape
  (an array of `{current:{time,...}, hourly:{time:[],pm2_5:[],pm10:[],nitrogen_dioxide:[],aerosol_optical_depth:[]}}`).
