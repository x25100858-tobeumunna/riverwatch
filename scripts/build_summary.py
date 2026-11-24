"""River Watch - build the stored history summary (run ONCE, offline).

Source: Open-Meteo Flood API (GloFAS v4 river discharge, Copernicus EMS, CC BY 4.0)
Period: 2016-01-01 to 2025-12-31 (10 full years of daily discharge).

Outputs
  data/history_daily.csv  - the raw daily series, one column per town (for checks)
  summary.json            - one row per town: chosen cell, mean, p95, p99,
                            winter high-flow events 2016/17-2024/25, and the
                            OPW gauge cross-check. The web page reads this file.

Percentiles use linear interpolation between closest ranks (= numpy default,
= Google Sheets / Excel PERCENTILE / PERCENTILE.INC), over every day in the period.
A high-flow event = a run of consecutive days with flow >= the town's p99, counted
inside each winter window 1 Oct - 31 Mar (a run is cut at the window edges).
"""
import json, os, urllib.request, urllib.parse, statistics, math, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "2016-01-01", "2025-12-31"
UA = {"User-Agent": "river-watch-student-project/1.0"}

# town, county, river, town centre (OSM Nominatim), chosen GloFAS cell, OPW gauge on same river
TOWNS = [
    ("Clonmel", "Tipperary", "Suir", (52.3550, -7.7039), (52.375, -7.725), ("16011", "Clonmel")),
    ("Fermoy", "Cork", "Blackwater", (52.1382, -8.2752), (52.175, -8.275), ("18117", "Fermoy Mill")),
    ("Mallow", "Cork", "Blackwater", (52.1374, -8.6450), (52.125, -8.625), ("18055", "Mallow Railway Br")),
    ("Bandon", "Cork", "Bandon", (51.7462, -8.7369), (51.775, -8.725), ("20002", "Curranure")),
    ("Enniscorthy", "Wexford", "Slaney", (52.5011, -6.5675), (52.525, -6.575), ("12001", "Scarawalsh")),
    ("Ennis", "Clare", "Fergus", (52.8435, -8.9837), (52.825, -9.025), ("27002", "Ballycorey")),
    ("Athlone", "Westmeath", "Shannon", (53.4228, -7.9426), (53.425, -7.975), ("26027", "Athlone")),
    ("Carrick-on-Shannon", "Leitrim", "Shannon", (53.9441, -8.0953), (53.925, -8.075), ("26085", "Jamestown")),
]
WINTERS = [f"{y}/{str(y + 1)[2:]}" for y in range(2016, 2025)]  # 2016/17 .. 2024/25


def get_json(url, cache):
    path = os.path.join(ROOT, "data", "cache", cache)
    if os.path.exists(path):
        return json.load(open(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180))
    json.dump(d, open(path, "w"))
    return d


def pct(vals, p):
    s = sorted(vals); k = (len(s) - 1) * p / 100; f = math.floor(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def km(a, b):
    dlat = (a[0] - b[0]) * 111.2; dlon = (a[1] - b[1]) * 111.2 * math.cos(math.radians(a[0]))
    return round(math.hypot(dlat, dlon), 1)


def corr(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (
        sum((x - ma) ** 2 for x in a) ** .5 * sum((y - mb) ** 2 for y in b) ** .5)


def winter_of(day):
    d = dt.date.fromisoformat(day)
    if d.month >= 10: return f"{d.year}/{str(d.year + 1)[2:]}"
    if d.month <= 3: return f"{d.year - 1}/{str(d.year)[2:]}"
    return None


q = urllib.parse.urlencode({
    "latitude": ",".join(str(t[4][0]) for t in TOWNS), "longitude": ",".join(str(t[4][1]) for t in TOWNS),
    "daily": "river_discharge", "start_date": START, "end_date": END})
glofas = get_json("https://flood-api.open-meteo.com/v1/flood?" + q, "glofas_2016_2025.json")
glofas = glofas if isinstance(glofas, list) else [glofas]

rows, daily = [], {}
for (town, county, river, centre, cell, (gid, gname)), g in zip(TOWNS, glofas):
    days, vals = g["daily"]["time"], g["daily"]["river_discharge"]
    series = {d: v for d, v in zip(days, vals) if v is not None}
    daily[town] = series
    v = list(series.values())
    p95, p99 = pct(v, 95), pct(v, 99)

    events = {w: 0 for w in WINTERS}; longest = {w: 0 for w in WINTERS}
    run, prev_w = 0, None
    for d in days:
        w = winter_of(d)
        hit = w in events and series.get(d) is not None and series[d] >= p99
        if hit and run and w == prev_w:
            run += 1
        elif hit:
            events[w] += 1; run = 1
        else:
            run = 0
        if hit: longest[w] = max(longest[w], run)
        prev_w = w
    first4, last4 = sum(events[w] for w in WINTERS[:4]), sum(events[w] for w in WINTERS[-4:])

    # OPW cross-check (measured flow on the same river) - mean and day-by-day correlation
    opw = get_json(f"https://waterlevel.ie/hydro-data/data/internet/stations/0/{gid}/Q/year.json", f"opw_{gid}.json")
    m = next(x for x in opw if x["ts_shortname"] == "WEB.Day.Mean")["data"]
    gauge = {t[:10]: val for t, val, _ in m if START <= t[:10] <= END and val is not None}
    common = [d for d in gauge if d in series]
    a, b = [series[d] for d in common], [gauge[d] for d in common]

    rows.append({
        "town": town, "county": county, "river": river,
        "town_lat": centre[0], "town_lon": centre[1],
        "cell_lat": g["latitude"], "cell_lon": g["longitude"], "cell_km_from_town": km(centre, (g["latitude"], g["longitude"])),
        "period": f"{START} to {END}", "days": len(v), "missing_days": len(days) - len(v),
        "mean_m3s": round(statistics.mean(v), 1), "p95_m3s": round(p95, 1), "p99_m3s": round(p99, 1),
        "max_m3s": round(max(v), 1), "max_date": max(series, key=series.get),
        "winter_events": events, "winter_longest_run_days": longest,
        "events_total": sum(events.values()), "events_first4": first4, "events_last4": last4,
        "check_gauge": f"OPW {gid} {gname} ({river})", "check_days": len(common),
        "check_gauge_mean_m3s": round(statistics.mean(b), 1), "check_model_mean_same_days_m3s": round(statistics.mean(a), 1),
        "check_ratio_model_to_gauge": round(statistics.mean(a) / statistics.mean(b), 2),
        "check_daily_correlation": round(corr(a, b), 3),
        "check_gauge_p99_m3s": round(pct(b, 99), 1),
    })

summary = {
    "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "source": "Open-Meteo Flood API (https://open-meteo.com/en/docs/flood-api), GloFAS v4 river discharge, "
              "Copernicus Emergency Management Service, CC BY 4.0",
    "check_source": "OPW hydrometric data, https://waterlevel.ie/hydro-data/ (measured daily mean flow), CC BY 4.0",
    "method": "p95/p99 = linear-interpolation percentiles of all daily values in the period. "
              "Event = run of consecutive days >= p99 inside 1 Oct-31 Mar; first4 = 2016/17-2019/20, last4 = 2021/22-2024/25.",
    "towns": rows,
}
json.dump(summary, open(os.path.join(ROOT, "summary.json"), "w"), indent=1, ensure_ascii=False)

with open(os.path.join(ROOT, "data", "history_daily.csv"), "w") as f:
    f.write("date," + ",".join(t[0] for t in TOWNS) + "\n")
    for d in glofas[0]["daily"]["time"]:
        f.write(d + "," + ",".join("" if daily[t[0]].get(d) is None else str(daily[t[0]][d]) for t in TOWNS) + "\n")

print(f"{'town':20}{'cell':>18}{'km':>5}{'mean':>7}{'p95':>7}{'p99':>7}{'ev':>4}{'f4':>4}{'l4':>4}   gauge mean  ratio  r")
for r in rows:
    print(f"{r['town']:20}{r['cell_lat']:>9},{r['cell_lon']:<8}{r['cell_km_from_town']:>5}{r['mean_m3s']:>7}{r['p95_m3s']:>7}"
          f"{r['p99_m3s']:>7}{r['events_total']:>4}{r['events_first4']:>4}{r['events_last4']:>4}   "
          f"{r['check_gauge_mean_m3s']:>8}  {r['check_ratio_model_to_gauge']:>5}  {r['check_daily_correlation']}")
