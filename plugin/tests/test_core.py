"""Offline tests for aqi-ops (no network). Run: python3 -m unittest discover -s plugin/tests"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from aqiops import aqi as A, fires as F, locations as L, openmeteo as OM  # noqa: E402


def fake_aq(pm25=100.0, pm10=200.0, hours_past=24, hours_fwd=72, spike_at=None):
    """Open-Meteo-shaped response: flat concentrations, optional spike in the forecast."""
    times = []
    for d in range(5):
        for h in range(24):
            times.append(f"2026-11-{7 + d:02d}T{h:02d}:00")
    n = hours_past + hours_fwd
    times = times[:n]
    p25 = [pm25] * n
    p10 = [pm10] * n
    if spike_at is not None:
        for i in range(spike_at, n):
            p25[i] = 300.0
    hourly = {"time": times, "pm2_5": p25, "pm10": p10, "nitrogen_dioxide": [60.0] * n,
              "sulphur_dioxide": [10.0] * n, "carbon_monoxide": [1500.0] * n, "ozone": [40.0] * n,
              "aerosol_optical_depth": [0.8] * n, "dust": [5.0] * n}
    return {"current": {"time": times[hours_past - 1], "pm2_5": pm25, "pm10": pm10, "us_aqi": 180},
            "hourly": hourly}


class TestAQI(unittest.TestCase):
    def test_breakpoint_edges(self):
        self.assertEqual(A.sub_index(30, "pm25"), 50)
        self.assertEqual(A.sub_index(60, "pm25"), 100)
        self.assertEqual(A.sub_index(250, "pm25"), 400)
        self.assertEqual(A.sub_index(1000, "pm25"), 500)
        self.assertEqual(A.sub_index(100, "pm10"), 100)
        self.assertIsNone(A.sub_index(None, "pm10"))

    def test_compute_driver_and_category(self):
        r = A.compute({"pm25": 150, "pm10": 200})
        self.assertEqual(r["driver"], "PM2.5")
        self.assertEqual(r["aqi"], 324)  # 301 + 99*(150-120)/130
        self.assertEqual(r["category"]["name"], "Very Poor")

    def test_co_in_mg(self):
        self.assertEqual(A.sub_index(1.5, "co"), 76)

    def test_matches_dashboard_tables(self):
        html = (ROOT.parent / "index.html").read_text()
        for key, js in (("pm25", "pm25"), ("pm10", "pm10")):
            m = re.search(js + r":\s*(\[\[.*?\]\])", html)
            self.assertIsNotNone(m, f"BP.{js} not found in index.html")
            table = [tuple(x) for x in json.loads(m.group(1))]
            self.assertEqual(table, [tuple(x) for x in A.BREAKPOINTS[key]])


class TestOpenMeteo(unittest.TestCase):
    def test_current_pm(self):
        r = OM.current(fake_aq(), {"name": "X", "lat": 0, "lon": 0})
        self.assertEqual(r["averages"]["PM2.5"], 100.0)
        self.assertEqual(r["aqi"], A.compute({"pm25": 100, "pm10": 200})["aqi"])

    def test_current_all_mode(self):
        r = OM.current(fake_aq(pm25=20, pm10=40), {"name": "X", "lat": 0, "lon": 0}, mode="all")
        self.assertIn("NO2", r["sub_indices"])
        self.assertEqual(r["driver"], "NO2")  # NO2 60 -> 76 beats PM

    def test_forecast_spike(self):
        r = fake_aq(spike_at=24 + 30)
        f = OM.forecast(r, {"name": "X", "lat": 0, "lon": 0})
        self.assertEqual(f["days"][0]["date"], "2026-11-07")
        self.assertGreater(f["days"][-1]["peak_rolling_aqi"], f["days"][0]["peak_rolling_aqi"])

    def test_wind(self):
        self.assertTrue(OM.is_north_westerly(310))
        self.assertFalse(OM.is_north_westerly(120))
        self.assertEqual(OM.compass(315), "NW")

    def test_url_multi_point(self):
        u = OM.aq_url(L.LOCATIONS[:2])
        self.assertIn("latitude=28.6315,28.6469", u)
        self.assertIn("timezone=Asia/Kolkata", u)


class TestLocations(unittest.TestCase):
    def test_resolve(self):
        self.assertEqual(len(L.resolve("all")), 12)
        self.assertEqual(L.resolve("noida")[0]["name"], "Noida Sector 62")
        self.assertEqual(L.resolve("Gurgaon")[0]["name"], "Gurugram")
        self.assertEqual(L.resolve("28.5,77.1")[0]["lat"], 28.5)
        self.assertEqual(len(L.resolve("noida; faridabad")), 2)

    def test_bearing(self):
        self.assertTrue(320 < L.bearing_deg(L.DELHI, (30.9, 75.85)) < 345)  # Ludhiana: NNW of Delhi
        self.assertEqual(F.region(30.9, 75.85), "Punjab (approx.)")    # Ludhiana
        self.assertEqual(F.region(30.21, 74.95), "Punjab (approx.)")   # Bathinda
        self.assertEqual(F.region(29.97, 76.85), "Haryana (approx.)")  # Kurukshetra
        self.assertEqual(F.region(29.8, 76.4), "Haryana (approx.)")    # Kaithal
        self.assertEqual(F.region(29.58, 74.32), "Rajasthan (approx.)")  # Hanumangarh
        self.assertEqual(F.region(28.98, 77.7), "Western UP (approx.)")  # Meerut


class TestFires(unittest.TestCase):
    CSV = ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,"
           "bright_ti5,frp,daynight\n"
           "30.9,75.85,330,0.4,0.4,2026-11-07,750,N,VIIRS,n,2.0NRT,290,20.5,D\n"
           "29.9,76.5,330,0.4,0.4,2026-11-07,750,N,VIIRS,h,2.0NRT,290,10.0,D\n"
           "28.0,78.0,330,0.4,0.4,2026-11-07,750,N,VIIRS,l,2.0NRT,290,99.0,D\n")

    def test_parse_and_summary(self):
        fl = F.parse_csv(self.CSV)
        self.assertEqual(len(fl), 2)  # low confidence dropped
        self.assertEqual(fl[0]["time"], "07:50 UTC")
        s = F.summarize(fl)
        self.assertEqual(s["count"], 2)
        self.assertEqual(s["upwind_nw_of_delhi"]["count"], 2)
        self.assertEqual(s["by_region"]["Punjab (approx.)"]["count"], 1)

    def test_schema_matches_dashboard(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fires.json"
            F.write_fires_json(F.parse_csv(self.CSV), p, "VIIRS_SNPP_NRT", 2)
            got = json.loads(p.read_text())
        ref = json.loads((ROOT.parent / "data" / "fires.json").read_text())
        self.assertEqual(set(got), set(ref))
        self.assertEqual(set(got["fires"][0]), set(ref["fires"][0]))

    def test_smoke_outlook(self):
        wind = {"daily": [{"date": "2026-11-08", "share_north_westerly": 0.8, "mean_wind_kmh": 6,
                           "min_boundary_layer_m": 150}]}
        o = F.smoke_outlook({"upwind_nw_of_delhi": {"frp_mw": 900}}, wind)
        self.assertEqual(o["days"][0]["smoke_transport_risk"], "high")
        o = F.smoke_outlook(None, {"daily": [{"date": "x", "share_north_westerly": 0, "mean_wind_kmh": 15,
                                              "min_boundary_layer_m": 900}]})
        self.assertEqual(o["days"][0]["smoke_transport_risk"], "low")


if __name__ == "__main__":
    unittest.main()
