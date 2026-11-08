#!/usr/bin/env python3
"""PostToolUse hook: after Claude edits tracker files, catch the mistakes that are easy to miss.

- index.html: BP.pm25 / BP.pm10 must still match the CPCB tables in aqiops/aqi.py.
- data/fires.json: must keep the schema index.html reads.
- any edited file: warn if it now contains something that looks like a hard-coded API key.

Exit 0 = fine/not relevant. Exit 2 = feedback shown to Claude (the edit itself already happened).
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

KEY_PATTERNS = [
    (re.compile(r"""(?i)(map_?key|firms[_a-z]*key|api[-_]?key|bot[_-]?token)['"]?\s*[:=,]\s*(default\s*=\s*)?['"]([A-Za-z0-9:_-]{20,})['"]"""),
     "an API key or token"),
    (re.compile(r"""['"][0-9a-f]{32}['"]"""), "a 32-hex-character string (FIRMS MAP_KEY format)"),
]


def problems(path: Path) -> list[str]:
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    if path.suffix in (".py", ".html", ".js", ".yml", ".yaml", ".sh", ".json") and path.name != "fires.json":
        for rx, what in KEY_PATTERNS:
            if rx.search(text):
                out.append(f"{path.name} appears to contain {what}. Read keys from env vars "
                           "(FIRMS_MAP_KEY, DATA_GOV_IN_KEY, TELEGRAM_BOT_TOKEN) instead of committing them.")
                break
    if path.name == "index.html" and "BP" in text:
        from aqiops.aqi import BREAKPOINTS
        for key in ("pm25", "pm10"):
            m = re.search(key + r":\s*(\[\[.*?\]\])", text)
            if not m:
                out.append(f"index.html: could not find BP.{key}; the AQI tables may have been renamed or removed.")
                continue
            try:
                got = [tuple(x) for x in json.loads(m.group(1))]
            except ValueError:
                out.append(f"index.html: BP.{key} is not a plain numeric array any more.")
                continue
            want = [tuple(x) for x in BREAKPOINTS[key]]
            if got != want:
                out.append(f"index.html: BP.{key} no longer matches the CPCB table in aqiops/aqi.py "
                           f"({want}). If CPCB changed the breakpoints, update both.")
    if path.name == "fires.json":
        try:
            d = json.loads(text)
            missing = {"source", "days", "bbox", "fetched_at", "fires"} - set(d)
            if missing:
                out.append(f"data/fires.json is missing keys {sorted(missing)} that index.html expects.")
            elif d["fires"] and {"lat", "lon", "date", "time", "frp", "confidence"} - set(d["fires"][0]):
                out.append("data/fires.json fire entries must have lat, lon, date, time, frp, confidence.")
        except ValueError as e:
            out.append(f"data/fires.json is not valid JSON: {e}")
    return out


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    fp = (event.get("tool_input") or {}).get("file_path")
    if not fp:
        return 0
    p = Path(fp)
    if not p.exists() or p.stat().st_size > 2_000_000:
        return 0
    found = problems(p)
    if found:
        print("aqi-ops check:\n- " + "\n- ".join(found), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
