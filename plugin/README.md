# aqi-ops: Delhi-NCR air quality for Claude Code

A Claude Code plugin that ships with the [NCR Air Quality Tracker](../README.md). Ask Claude
"what's the AQI in Noida?", "will Delhi be better tomorrow?" or "are the stubble fires reaching NCR?" and
get numbers computed from open satellite-derived data, not guesses.

## Install

```
/plugin marketplace add bosons14/ncr-aqi-tracker
/plugin install aqi-ops@ncr-aqi-tracker
```

Needs Python 3.10+ and either [uv](https://docs.astral.sh/uv/) (recommended, nothing else to install) or
`pip install "mcp>=1.2"`.

### Optional keys (all free)

| Env var | Unlocks | Get it |
|---|---|---|
| `FIRMS_MAP_KEY` | Farm fires, smoke outlook with fires, `refresh_fires_json` | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| `DATA_GOV_IN_KEY` | CPCB ground-station comparison | https://data.gov.in (My Account -> API key) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Sending forecast alerts | @BotFather on Telegram |

Pollutant and weather data (Open-Meteo) need no key.

## What's inside

**Skills**
- `air-quality-report` - AQI, category, driver pollutant, trend and health line for any NCR place.
- `stubble-smoke` - FIRMS fire counts and fire power over Punjab/Haryana + wind, mixing layer -> smoke risk.
- `aqi-dashboard` - run, extend and deploy the tracker (`index.html`, `fetch_fires.py`, new data layers).

**Agent**: `air-quality-analyst` - explains pollution episodes and compares model vs CPCB stations.

**MCP tools** (`aqi-ops` server)

| Tool | What it does |
|---|---|
| `current_aqi` | CPCB AQI now for one, several (`;`) or all 12 NCR points; `mode: all` adds NO2, SO2, CO, O3 |
| `aqi_forecast` | Daily AQI and peak hour for up to 5 days, plus wind and mixing-layer outlook |
| `compute_aqi` | Offline CPCB AQI calculator |
| `fire_activity` | FIRMS fires: count, FRP by date and region, upwind share, strongest fires |
| `smoke_outlook` | Low/moderate/high stubble-smoke transport risk per day |
| `refresh_fires_json` | Writes the dashboard's `data/fires.json` |
| `forecast_alerts` | Places/times where forecast AQI crosses a threshold; optional Telegram post |
| `cpcb_compare` | Model vs nearest CPCB stations (data.gov.in) |
| `request_urls`, `analyze_open_meteo_json` | Fallback when the server has no network: fetch elsewhere, compute here |
| `aqi_status` | Version, keys set, connectivity |

**Hook**: after Claude edits tracker files, checks that `BP` in `index.html` still matches the CPCB tables,
that `data/fires.json` keeps its schema, and that no API key got hard-coded.

## How the AQI is computed

Indian National AQI (CPCB): trailing 24-h means for PM2.5, PM10, NO2, SO2 and 8-h means for CO and O3,
linear interpolation inside each band, AQI = highest sub-index. Default mode uses PM2.5 and PM10 only,
matching the dashboard. Concentrations come from the Copernicus CAMS model (which assimilates
Sentinel-5P, MODIS and other satellite data) at roughly 10-40 km resolution, so values are an
**estimate, not an official CPCB reading**, and roadside hotspots usually read higher on the ground.

The smoke outlook is a heuristic (upwind fire power x north-westerly wind share x shallow mixing layer x
calm winds), not a source attribution.

## Develop

```bash
python3 -m unittest discover -s plugin/tests     # offline tests, no network needed
claude --plugin-dir ./plugin                     # try the plugin from a checkout
```
