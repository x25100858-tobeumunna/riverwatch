"""Scan GloFAS grid cells around each town (Open-Meteo Flood API) and report
the mean daily discharge of each cell for 2024, so we can pick the cell that
sits on the town's named river (the main river carries far more flow than
side streams, and the snapped cell location shows where it is)."""
import json, urllib.request, urllib.parse, statistics, sys

TOWNS = {  # OpenStreetMap / Nominatim town centres (place=town)
    "Clonmel": (52.3550, -7.7039),
    "Fermoy": (52.1382, -8.2752),
    "Mallow": (52.1374, -8.6450),
    "Bandon": (51.7462, -8.7369),
    "Enniscorthy": (52.5011, -6.5675),
    "Ennis": (52.8435, -8.9837),
    "Athlone": (53.4228, -7.9426),
    "Carrick-on-Shannon": (53.9441, -8.0953),
}
STEP, N = 0.05, 2  # +/- 0.10 degrees in 0.05 steps -> 5x5 cells


def fetch(lats, lons, start, end):
    q = urllib.parse.urlencode({
        "latitude": ",".join(f"{x:.3f}" for x in lats),
        "longitude": ",".join(f"{x:.3f}" for x in lons),
        "daily": "river_discharge", "start_date": start, "end_date": end})
    with urllib.request.urlopen("https://flood-api.open-meteo.com/v1/flood?" + q, timeout=60) as r:
        d = json.load(r)
    return d if isinstance(d, list) else [d]


out = {}
for town, (lat, lon) in TOWNS.items():
    lats, lons = [], []
    for i in range(-N, N + 1):
        for j in range(-N, N + 1):
            lats.append(lat + i * STEP); lons.append(lon + j * STEP)
    res = fetch(lats, lons, "2024-01-01", "2024-12-31")
    cells = {}
    for qlat, qlon, d in zip(lats, lons, res):
        key = (d["latitude"], d["longitude"])
        v = [x for x in d["daily"]["river_discharge"] if x is not None]
        if v:
            cells[key] = round(statistics.mean(v), 1)
    ranked = sorted(cells.items(), key=lambda kv: -kv[1])
    out[town] = ranked
    print(f"\n{town} ({lat}, {lon}) - top cells by 2024 mean flow:")
    for (clat, clon), m in ranked[:6]:
        print(f"   cell {clat:.3f},{clon:.3f}  mean {m:7.1f} m3/s")

json.dump({t: [[c[0][0], c[0][1], c[1]] for c in r] for t, r in out.items()},
          open(sys.argv[1] if len(sys.argv) > 1 else "cell_scan.json", "w"), indent=1)
