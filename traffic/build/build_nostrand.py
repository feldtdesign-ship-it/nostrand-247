import json, os, base64, datetime, collections, re
S = os.path.dirname(os.path.abspath(__file__))
def J(n):
    p = os.path.join(S, n)
    if not os.path.exists(p) or os.path.getsize(p) < 3: return None
    r = json.load(open(p))
    return None if isinstance(r, dict) else r

# day counts for summer 2026
days = collections.Counter(); d = datetime.date(2026, 6, 1)
while d <= datetime.date(2026, 8, 31): days[(d.weekday() + 1) % 7] += 1; d += datetime.timedelta(days=1)

# G hourly by dow
g_hourly = {dw: [0.0] * 24 for dw in range(7)}
for x in (J('mta_hourly.json') or []):
    g_hourly[int(x['dow'])][int(x['hr'])] = round(float(x['riders']) / days[int(x['dow'])], 1)

# bus hourly by dow from raw rows: hour text like "2026-06-01 05:00:00 PM" or ISO
bus_hourly = {dw: [0.0] * 24 for dw in range(7)}
raw = J('bus_raw.json') or []
def parse_hour(s):
    m = re.search(r'(\d{1,2}):\d{2}:\d{2}\s*(AM|PM)', s, re.I)
    if m:
        h = int(m.group(1)) % 12; return h + (12 if m.group(2).upper() == 'PM' else 0)
    m = re.search(r'T(\d{2}):', s)
    return int(m.group(1)) if m else None
for x in raw:
    dt = datetime.date.fromisoformat(x['date'][:10]); dw = (dt.weekday() + 1) % 7
    h = parse_hour(x.get('hour', ''));
    if h is None: continue
    bus_hourly[dw][h] += float(x.get('boardings') or 0) + float(x.get('alightings') or 0)
for dw in bus_hourly: bus_hourly[dw] = [round(v / days[dw], 1) for v in bus_hourly[dw]]
print('bus raw rows', len(raw), 'weekday bus/day', round(sum(sum(bus_hourly[d]) for d in (1,2,3,4,5)) / 5))

# cars
atr = json.load(open(os.path.join(S,'atr_summary.json'))) if os.path.exists(os.path.join(S,'atr_summary.json')) else {}
car_hourly = atr.get('hourly', [0] * 24); car_day = round(sum(v for _, v in atr.get('days', [])) / max(1, len(atr.get('days', []))))

# G months 2020..2026
g_months = []
for n in ('mta_hist.json', 'mta_2025.json'):
    for r in (J(n) or []):
        m = r['month'][:7]
        if not any(p[0] == m for p in g_months): g_months.append([m, float(r['riders'])])
# fill 2025+ months from the daily file when the monthly query timed out
mon = collections.defaultdict(float)
for r in (J('mta_daily.json') or []): mon[r['day'][:7]] += float(r['riders'])
for m, v in mon.items():
    if not any(p[0] == m for p in g_months): g_months.append([m, v])
g_months.sort(); g_months = [p for p in g_months if p[0] <= '2026-08']

# bus route months
bus_months = collections.defaultdict(dict)
for n in ('bus_route_hist.json', 'bus_route_2025.json'):
    for r in (J(n) or []):
        m = r['month'][:7]
        if m <= '2026-08': bus_months[r['bus_route']][m] = float(r['riders'])
bus_months = {k: sorted([[m, v] for m, v in d.items()]) for k, d in bus_months.items()}

# stop months (five stops, all routes)
stop = collections.defaultdict(float)
for r in (J('bus_monthly.json') or []):
    m = r['month'][:7]
    if m <= '2026-07': stop[m] += float(r['b']) + float(r['a'])
stop_months = sorted([[m, round(v)] for m, v in stop.items()])

# daily + weather
daily = []
w = json.load(open(os.path.join(S, 'weather.json')))['daily']
wx = {t: (w['temperature_2m_max'][i], w['precipitation_sum'][i] or 0.0, w['snowfall_sum'][i] or 0.0) for i, t in enumerate(w['time'])}
for r in (J('mta_daily.json') or []):
    dt = r['day'][:10]
    if dt in wx and '2025-01-01' <= dt <= '2026-08-31' and wx[dt][0] is not None:
        t, p, s = wx[dt]; daily.append([dt, round(float(r['riders'])), round(t, 1), round(p, 2), round(s, 2)])

# cams
cams = []
for c in (J(os.path.join('ring', 'ring.json')) or []):
    fp = os.path.join(S, c['file'])
    if os.path.exists(fp) and os.path.getsize(fp) > 1000:
        cams.append({'name': c['name'], 'dist': c['dist'], 'id': c['id'], 't': 'Wed 9 Sep 2026, 7:19 pm', 'src': 'data:image/jpeg;base64,' + base64.b64encode(open(fp, 'rb').read()).decode()})

data = {'g_hourly': g_hourly, 'bus_hourly': bus_hourly, 'car_hourly': car_hourly, 'car_day': car_day,
        'g_months': g_months, 'bus_months': bus_months, 'stop_months': stop_months, 'daily': daily, 'cams': cams}
tpl = open(os.path.join(S, 'nostrand_template.html')).read()
out = tpl.replace('__DATA__', json.dumps(data, separators=(',', ':')))
open(os.path.join(S, 'index.html'), 'w').write(out)
R="/Users/michaelweinfeld/Documents/2026/PJ O'Rourke/nostrand-247/traffic"
if os.path.isdir(R): open(os.path.join(R,'index.html'),'w').write(out)
print(f"built: g_months={len(g_months)} bus_routes={list(bus_months)} stop_months={len(stop_months)} daily={len(daily)} cams={len(cams)} car_day={car_day} size={len(out)//1024}KB")
