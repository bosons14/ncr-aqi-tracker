# NCR Air Quality Tracker

A live air-quality dashboard for Delhi-NCR, built on open satellite-derived data.

- **Map and table** of 12 NCR locations (Delhi, Noida, Greater Noida, Ghaziabad, Gurugram, Faridabad, Sonipat), coloured by **Indian AQI** (CPCB categories, computed from 24-h PM2.5/PM10).
- **Detail panel** with the past 24 h plus a 4-day forecast of PM2.5, PM10 and NO₂, and the current Delhi wind (the north-westerly wind carries Punjab/Haryana stubble smoke into NCR).
- **Farm-fire overlay** from NASA FIRMS (VIIRS) over Punjab and Haryana.

## Data sources

| Layer | Source | Key needed? |
|---|---|---|
| PM2.5, PM10, NO₂, CO, O₃, SO₂, AOD, dust | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) (Copernicus CAMS model, which assimilates Sentinel-5P, MODIS and other satellite data) | No |
| Wind, temperature, humidity | [Open-Meteo Forecast API](https://open-meteo.com/en/docs) | No |
| Basemap | OpenStreetMap tiles by default; [CARTO dark basemap](https://carto.com/basemaps/apikey/) if you set `CARTO_KEY` in `index.html` | CARTO: free key |
| Active fires | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/) VIIRS/MODIS | Free MAP_KEY |

> The AQI is an estimate from modelled concentrations (CAMS ~ 10–40 km resolution), not an official CPCB station reading.

## Run it

```bash
# 1. (optional) farm fires — get a free key at https://firms.modaps.eosdis.nasa.gov/api/map_key/
python fetch_fires.py --key YOUR_MAP_KEY --days 2

# 2. serve the folder (browsers block fetch() from file://, so use a local server)
python -m http.server 8000
# open http://localhost:8000
```

The pollutant data loads straight from Open-Meteo in the browser, so with no fire data you can simply open `index.html`.

To keep fires fresh, schedule step 1, e.g. with cron every 3 hours:
```
0 */3 * * * cd /path/to/ncr-aqi-tracker && FIRMS_MAP_KEY=xxx python3 fetch_fires.py
```

## Roadmap (good next prompts for Claude Code)

1. **Sentinel-5P NO₂ / aerosol maps**: pull TROPOMI L2 from Copernicus Data Space (openEO or STAC) and render a raster overlay.
2. **MOSDAC INSAT-3DR AOD**: ISRO's aerosol product over India, through the MOSDAC download API.
3. **CPCB ground truth**: compare with the data.gov.in CPCB real-time AQI feed and plot model against station.
4. **Alerts**: Telegram/WhatsApp message when forecast AQI crosses "Very Poor" (>300).
5. **Fire–smoke attribution**: back-trajectories using wind fields (e.g. HYSPLIT) to estimate how much of NCR PM2.5 comes from fires.
6. **Deploy**: GitHub Pages for the page plus a GitHub Action that runs `fetch_fires.py` on a schedule and commits `data/fires.json`.
