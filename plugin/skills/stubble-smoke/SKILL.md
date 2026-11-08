---
name: stubble-smoke
description: "This skill should be used when the user asks \"how bad are the stubble fires\", \"are farm fires affecting Delhi\", \"parali\", \"how many fires in Punjab today\", \"will smoke reach NCR\", \"refresh the fire data\", or runs /stubble-smoke. Uses NASA FIRMS VIIRS/MODIS active fires over Punjab and Haryana with the Delhi wind forecast to judge whether crop-residue smoke is reaching Delhi-NCR."
metadata:
  version: "0.1.0"
---

# Stubble smoke and farm fires

## Procedure

1. **Check the key.** Fire data needs a free NASA FIRMS MAP_KEY in `FIRMS_MAP_KEY`. If `fire_activity`
   says it is missing, tell the user where to get one (https://firms.modaps.eosdis.nasa.gov/api/map_key/)
   and how to set it, and continue with the weather-only `smoke_outlook`.
2. **Fires:** `fire_activity` with `days` 1-3 for "today/now", up to 7-10 for a season trend. Use
   `VIIRS_SNPP_NRT` (default) or `VIIRS_NOAA20_NRT`/`VIIRS_NOAA21_NRT` for a second overpass; `MODIS_NRT` is
   coarser. Report count, total fire radiative power (FRP, MW), split by date and by region (labels are
   approximate, from coordinates), and the strongest detections with distance/bearing from Delhi.
3. **Transport:** `smoke_outlook` for the next days: NW wind share, wind speed and minimum mixing-layer
   height, combined into a low/moderate/high smoke-transport risk. Explain the reasons it lists.
4. **Tie to AQI** when useful: `aqi_forecast` for Delhi, and note whether the forecast peak lines up with the
   high-risk days.
5. **Be careful with attribution.** This is a heuristic. Say "likely contributing" rather than giving a
   percentage share. A real estimate needs back-trajectories (HYSPLIT) or a chemical transport model; the
   repo roadmap lists this as a next step and the `air-quality-analyst` agent can scope it.
6. **Dashboard refresh:** if the user wants the map's fire layer updated, call `refresh_fires_json`
   (writes `data/fires.json` in the project); remind them the page reads it when "Show farm fires" is
   ticked.

Notes: FIRMS times are UTC (IST = UTC+5:30). VIIRS S-NPP passes over north India around 13:30 local time,
so afternoon fires are well captured and evening burning less so. Low-confidence detections are dropped.
