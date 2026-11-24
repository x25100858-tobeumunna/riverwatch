"""For each town, fetch 2016-2025 daily GloFAS discharge (Open-Meteo Flood API)
for the candidate cells found by scan_cells.py, and compare each with the OPW
gauge on the town's named river: mean flow ratio and daily correlation.
The cell that tracks the gauge best (high correlation, plausible mean, close to
the town) is the one River Watch uses."""
import json, urllib.request, urllib.parse, statistics, sys

UA = {"User-Agent": "river-watch-student-project/1.0"}
START, END = "2016-01-01", "2025-12-31"
TOWNS = {  # town: (OPW reference gauge, candidate GloFAS cells from the scan)
    "Clonmel": ("16011", [(52.375, -7.725), (52.375, -7.675), (52.375, -7.625), (52.375, -7.775)]),
    "Fermoy": ("18117", [(52.175, -8.275), (52.175, -8.225), (52.125, -8.225), (52.125, -8.325)]),
    "Mallow": ("18055", [(52.125, -8.625), (52.125, -8.675), (52.125, -8.575), (52.175, -8.575)]),
    "Bandon": ("20002", [(51.725, -8.675), (51.775, -8.725), (51.725, -8.775), (51.675, -8.625)]),
    "Enniscorthy": ("12001", [(52.525, -6.575), (52.525, -6.625), (52.475, -6.625), (52.575, -6.625)]),
    "Ennis": ("27002", [(52.825, -9.025), (52.875, -9.025), (52.775, -8.975), (52.825, -8.975)]),
    "Athlone": ("26027", [(53.425, -7.975), (53.425, -8.025), (53.375, -7.975), (53.475, -8.025)]),
    "Carrick-on-Shannon": ("26085", [(53.925, -8.075), (53.925, -8.025), (53.875, -8.025), (53.925, -8.125)]),
}


def opw(g):
    url = f"https://waterlevel.ie/hydro-data/data/internet/stations/0/{g}/Q/year.json"
    s = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
    m = next(x for x in s if x["ts_shortname"] == "WEB.Day.Mean")["data"]
    return {t[:10]: v for t, v, q in m if START <= t[:10] <= END and v is not None}


def glofas(cells):
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(c[0]) for c in cells), "longitude": ",".join(str(c[1]) for c in cells),
        "daily": "river_discharge", "start_date": START, "end_date": END})
    d = json.load(urllib.request.urlopen("https://flood-api.open-meteo.com/v1/flood?" + q, timeout=120))
    d = d if isinstance(d, list) else [d]
    return [dict(zip(x["daily"]["time"], x["daily"]["river_discharge"])) for x in d]


def corr(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / (sum((x - ma) ** 2 for x in a) ** .5 * sum((y - mb) ** 2 for y in b) ** .5)


report = {}
for town, (g, cells) in TOWNS.items():
    gauge = opw(g)
    rows = []
    for cell, series in zip(cells, glofas(cells)):
        days = [d for d in gauge if series.get(d) is not None]
        a = [series[d] for d in days]; b = [gauge[d] for d in days]
        allv = [v for v in series.values() if v is not None]
        rows.append(dict(cell=cell, glofas_mean=round(statistics.mean(allv), 1),
                         gauge_mean_same_days=round(statistics.mean(b), 1), r=round(corr(a, b), 3), n=len(days)))
    report[town] = dict(gauge=g, cells=rows)
    print(f"\n{town} vs OPW {g}")
    for r in rows:
        print(f"  cell {r['cell']}  GloFAS mean {r['glofas_mean']:6.1f}  gauge mean {r['gauge_mean_same_days']:6.1f}  r={r['r']:.3f}  n={r['n']}")
json.dump(report, open(sys.argv[1], "w"), indent=1)
