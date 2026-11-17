#!/usr/bin/env python3
"""Filter the Valley Metro GTFS feed down to light rail / streetcar (A Line, B Line, S Line)
and write trimmed CSVs that load.sql can COPY straight into the tables.

usage: python3 prep_gtfs.py <folder with the unzipped GTFS .txt files> <output folder>

What it does with this particular feed
- Rail = routes.txt rows with route_type 0 AND route_division VMR (this drops the PHX Sky Train).
- The feed has no calendar.txt, only calendar_dates.txt. The weekday pattern is read from the
  end of each service_id (for example ..._1111100 = Mon-Fri, ..._0000010 = Sat, ..._0000001 = Sun)
  and start/end dates are the first and last dates listed for that service in calendar_dates.txt.
- A platform stop with a parent_station is folded into the parent, so one station = one row.
- transfers.txt only lists Sky Train links, so transfers_to is built from nearby station pairs
  (under 300 m apart, served by different sets of rail lines). min_transfer_seconds is an estimate:
  walking distance at 1.2 m/s plus 60 seconds.
"""
import csv, sys, os, re, math

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

def rows(name):
    with open(os.path.join(src, name), newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            yield {k.strip(): (v or '').strip() for k, v in r.items() if k}

def write(name, header, data):
    with open(os.path.join(out, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(data)
    print(f'{name}: {len(data)} rows')

# ---- routes
routes = [r for r in rows('routes.txt')
          if r['route_type'] == '0' and r.get('route_division', 'VMR') == 'VMR']
route_ids = {r['route_id'] for r in routes}
print('rail routes:', sorted(route_ids))
write('route.csv', ['route_id', 'short_name', 'long_name', 'mode', 'color'],
      [[r['route_id'], r.get('route_short_name', ''), r.get('route_long_name', ''), 'rail',
        (r.get('route_color') or '').upper()] for r in routes])

# ---- trips
trips = [t for t in rows('trips.txt') if t['route_id'] in route_ids]
trip_ids = {t['trip_id'] for t in trips}
service_ids = {t['service_id'] for t in trips}
write('trip.csv', ['trip_id', 'route_id', 'service_id', 'direction', 'headsign'],
      [[t['trip_id'], t['route_id'], t['service_id'], t.get('direction_id') or '0',
        t.get('trip_headsign', '')] for t in trips])

# ---- service calendar
days = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
cal_rows = []
if os.path.exists(os.path.join(src, 'calendar.txt')):
    for c in rows('calendar.txt'):
        if c['service_id'] in service_ids:
            cal_rows.append([c['service_id']] + [('t' if c[d] == '1' else 'f') for d in days] +
                            [c['start_date'], c['end_date']])
else:
    dates = {}
    for r in rows('calendar_dates.txt'):
        if r['service_id'] in service_ids and r['exception_type'] == '1':
            dates.setdefault(r['service_id'], []).append(r['date'])
    for sid in sorted(service_ids):
        m = re.search(r'_([01]{7})$', sid)
        if not m or sid not in dates:
            print('WARNING: cannot build a calendar row for service', sid)
            continue
        flags = ['t' if ch == '1' else 'f' for ch in m.group(1)]
        cal_rows.append([sid] + flags + [min(dates[sid]), max(dates[sid])])
write('service_calendar.csv', ['service_id'] + list(days) + ['start_date', 'end_date'], cal_rows)

# ---- stop times and stations
stops = {s['stop_id']: s for s in rows('stops.txt')}
def station_of(stop_id):
    s = stops.get(stop_id)
    return s['parent_station'] if s and s.get('parent_station') else stop_id

stop_time, used, line_set, skipped = [], set(), {}, 0
trip_route = {t['trip_id']: t['route_id'] for t in trips}
for st in rows('stop_times.txt'):
    if st['trip_id'] not in trip_ids:
        continue
    arr = st.get('arrival_time') or st.get('departure_time')
    dep = st.get('departure_time') or st.get('arrival_time')
    if not arr:
        skipped += 1
        continue
    sid = station_of(st['stop_id'])
    used.add(sid)
    line_set.setdefault(sid, set()).add(trip_route[st['trip_id']])
    stop_time.append([st['trip_id'], st['stop_sequence'], sid, arr, dep])
write('stop_time.csv', ['trip_id', 'stop_sequence', 'station_id', 'arrival_time', 'departure_time'], stop_time)
if skipped:
    print(f'WARNING: {skipped} stop_times rows had no time and were skipped')

stations = [sid for sid in sorted(used) if sid in stops]
write('station.csv', ['station_id', 'name', 'latitude', 'longitude', 'zone_id'],
      [[sid, stops[sid].get('stop_name', ''), stops[sid].get('stop_lat', ''),
        stops[sid].get('stop_lon', ''), stops[sid].get('zone_id', '')] for sid in stations])

# ---- transfers: real rows first (rail-to-rail only), then nearby pairs
transfers = {}
if os.path.exists(os.path.join(src, 'transfers.txt')):
    for t in rows('transfers.txt'):
        a, b = station_of(t['from_stop_id']), station_of(t['to_stop_id'])
        if a in used and b in used and a != b:
            transfers[(a, b)] = t.get('min_transfer_time') or '60'
real = len(transfers)

def metres(a, b):
    la1, lo1, la2, lo2 = (float(stops[a]['stop_lat']), float(stops[a]['stop_lon']),
                          float(stops[b]['stop_lat']), float(stops[b]['stop_lon']))
    return math.hypot((la1 - la2) * 111000, (lo1 - lo2) * 111000 * math.cos(math.radians(la1)))

for i, a in enumerate(stations):
    for b in stations[i + 1:]:
        if line_set[a] != line_set[b]:
            d = metres(a, b)
            if d < 300:
                secs = str(round(d / 1.2) + 60)
                transfers.setdefault((a, b), secs)
                transfers.setdefault((b, a), secs)
print(f'transfers: {real} from transfers.txt, {len(transfers) - real} derived from station distance')
write('transfers_to.csv', ['from_station_id', 'to_station_id', 'min_transfer_seconds'],
      [[a, b, s] for (a, b), s in sorted(transfers.items())])
