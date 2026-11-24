"""Verification step (offline, run once): download measured daily mean flow
from the OPW hydrometric network (waterlevel.ie/hydro-data) for gauges on each
town's named river, and compare 2016-2025 mean / p95 / p99 with the GloFAS
cells from the Open-Meteo Flood API. OPW data is not CORS-enabled, so the web
page itself cannot use it; we use it here only to check we picked the right river."""
import json, urllib.request, sys, statistics

GAUGES = ["16011", "18117", "18107", "18106", "18003", "18055", "18050", "18002",
          "20001", "20002", "12001", "12002", "27002", "27066", "26027", "26333", "26324"]
START, END = "2016-01-01", "2025-12-31"


def pct(vals, p):  # linear interpolation, same as numpy default / Excel PERCENTILE.INC
    s = sorted(vals); k = (len(s) - 1) * p / 100; f = int(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


out = {}
for g in GAUGES:
    url = f"https://waterlevel.ie/hydro-data/data/internet/stations/0/{g}/Q/year.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "river-watch-student-project/1.0"})
        series = json.load(urllib.request.urlopen(req, timeout=60))
    except Exception as e:
        print(g, "no Q series:", e); continue
    mean = next((s for s in series if s["ts_shortname"] == "WEB.Day.Mean"), None)
    vals = [v for t, v, q in mean["data"] if START <= t[:10] <= END and v is not None]
    if len(vals) < 300:
        print(g, f"only {len(vals)} daily means in period"); continue
    first = mean["data"][0][0][:10]
    out[g] = dict(n=len(vals), first=first, mean=round(statistics.mean(vals), 1),
                  p95=round(pct(vals, 95), 1), p99=round(pct(vals, 99), 1))
    print(g, out[g])
json.dump(out, open(sys.argv[1], "w"), indent=1)
