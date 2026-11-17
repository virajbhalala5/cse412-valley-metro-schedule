# Valley Metro Light Rail Schedule App

CSE 412 Database Management, Phase 3, **Group 23**
(Viraj Bhalala, Jayanth Kesana, Tejas Gupta, Ekansh Gupta)

A small web app (Flask + PostgreSQL) for browsing and managing the Valley Metro light rail schedule
(A Line, B Line, S Line streetcar). It uses the database we built in Phase 2.

## What it does
- **Interactive map:** a real street map (OpenStreetMap, needs internet) with the real track of each line and the stations drawn from the database. Zoom, drag, hide a line, click a station to see its next trains. Without internet it shows a plain line diagram instead.
- **Next trains:** pick a station, date and time and see the next 10 departures (query)
- **Trip planner:** direct trains between two stations with ride time (query with a self-join)
- **Line summary:** trips, stations and first/last departure per line for any day (aggregate query)
- **Stations and station pages:** live filter, next departures and walking transfers
- **Trips:** search and filter, open a trip to see all its stops on a timeline
- **Add trip** (insert), **edit trip** / shift times / fix one stop (update), **delete trip** (delete, stop times go with it)
- Login is needed for add, edit and delete. Demo account: `admin` / `admin123`

## Run it (Mac)
You need Python 3.10+ and PostgreSQL (`brew install postgresql`, and have it running).

```bash
git clone <this repo> && cd valley-metro-app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./db/setup.sh            # creates database "transit" and loads the data
python app.py            # open http://127.0.0.1:5000
```

Expected output of `./db/setup.sh`: `3 routes, 71 stations, 2786 trips, 55075 stop_times`.

Other ways to load the database:
- From the dump: `createdb transit && psql -d transit -f db/transit_dump.sql`
- Different connection: `export DATABASE_URL="host=localhost dbname=transit user=you password=..."`

The `app_user` table (login) is created automatically the first time the app starts.

## Folder layout
```
app.py             Flask app (all routes and SQL)
templates/, static/   pages, styling, map and small scripts (no outside libraries)
db/schema.sql      7 tables from Phase 2, plus route_shape (track of each line) and a station_line view
db/load.sql        loads the CSVs in db/data/
db/data/           rail-only Valley Metro GTFS data as CSV (including route_shape.csv, the real track of each line)
db/transit_dump.sql  full database dump (schema + data)
db/task3.sql       the Phase 2 SELECT / INSERT / UPDATE / DELETE script
db/prep_gtfs.py    script that turned the GTFS feed into the CSVs
```

Data source: Valley Metro GTFS feed (valleymetro.org). Rail only (route type 0, Valley Metro Rail).
