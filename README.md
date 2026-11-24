
# River Watch

Decision support for a (fictional) flood response team covering eight Irish towns. Live page: https://x25100858-tobeumunna.github.io/riverwatch/

**AI can make mistakes; a person makes the final decision.**

## How it works
- `index.html`: the whole tool. On every question it reads the Team Sheet (Google Sheets CSV), the 3-day river flow forecast (Open-Meteo Flood API, GloFAS) and Met Éireann warnings. It applies the Flood Plan in code, then asks an AI model (the user's own key, stored only in their browser) to explain the result.
- `summary.json`: the stored history summary (one row per town: chosen GloFAS cell, mean, p95, p99, winter high-flow events 2016/17–2024/25, OPW gauge cross-check). It is computed once by `scripts/build_summary.py`.
- `data/county_codes.json`: Met Éireann warning region codes mapped to counties.
- `data/history_daily.csv`: the 2016–2025 daily series behind `summary.json`, kept for checking.
- `scripts/`: one-off scripts (cell scan, gauge check, summary build).

No API key is stored anywhere in this repository.

## Sources and attribution
- River flow forecast and history: GloFAS v4, Copernicus Emergency Management Service, via Open-Meteo (open-meteo.com), CC BY 4.0.
- Weather warnings: Copyright Met Éireann. Source met.ie. CC BY 4.0. Met Éireann does not accept any liability whatsoever for any error or omission in the data, their availability, or for any loss or damage arising from their use. Modified: filtered to rain warnings and matched to towns.
- Gauge cross-check: contains Irish Public Sector Data (OPW, waterlevel.ie), CC BY 4.0.
- Town locations: © OpenStreetMap contributors (ODbL).
