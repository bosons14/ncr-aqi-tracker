#!/bin/sh
# Launch the aqi-ops MCP server. Prefers uv (no global install needed), falls back to python3 + pip'd mcp.
HERE="$(cd "$(dirname "$0")" && pwd)"
if command -v uv >/dev/null 2>&1; then
  exec uv run --quiet --no-project --with "mcp>=1.2,<3" python "$HERE/aqi_mcp.py"
fi
PY="${AQIOPS_PYTHON:-python3}"
if ! "$PY" -c "import mcp" >/dev/null 2>&1; then
  echo "aqi-ops: the 'mcp' Python package is missing. Run: $PY -m pip install 'mcp>=1.2'  (or install uv)" >&2
  exit 1
fi
exec "$PY" "$HERE/aqi_mcp.py"
