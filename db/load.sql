-- CSE 412 Phase 2 - Group 23: load the rail-only GTFS CSVs (made by prep_gtfs.py) with COPY.
-- Run from the folder that contains the CSVs:   psql -d transit -f load.sql
-- (\copy reads the files on your machine; the server-side COPY form works the same way.)

BEGIN;

\copy route            (route_id, short_name, long_name, mode, color)                     FROM 'route.csv'            WITH (FORMAT csv, HEADER true)
\copy station          (station_id, name, latitude, longitude, zone_id)                  FROM 'station.csv'          WITH (FORMAT csv, HEADER true)
\copy service_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date) FROM 'service_calendar.csv' WITH (FORMAT csv, HEADER true)
\copy trip             (trip_id, route_id, service_id, direction, headsign)              FROM 'trip.csv'             WITH (FORMAT csv, HEADER true)
\copy stop_time        (trip_id, stop_sequence, station_id, arrival_time, departure_time) FROM 'stop_time.csv'       WITH (FORMAT csv, HEADER true)
\copy transfers_to     (from_station_id, to_station_id, min_transfer_seconds)            FROM 'transfers_to.csv'     WITH (FORMAT csv, HEADER true)

-- Serves is not a GTFS file. Derive it: for each route and direction take the longest trip
-- as the pattern and number its stations in order.
INSERT INTO serves (route_id, station_id, direction, stop_order)
WITH pattern AS (
    SELECT DISTINCT ON (t.route_id, t.direction) t.route_id, t.direction, t.trip_id
    FROM trip t
    JOIN stop_time st ON st.trip_id = t.trip_id
    GROUP BY t.route_id, t.direction, t.trip_id
    ORDER BY t.route_id, t.direction, COUNT(*) DESC, t.trip_id
),
first_visit AS (
    SELECT p.route_id, p.direction, st.station_id, MIN(st.stop_sequence) AS seq
    FROM pattern p
    JOIN stop_time st ON st.trip_id = p.trip_id
    GROUP BY p.route_id, p.direction, st.station_id
)
SELECT route_id, station_id, direction,
       ROW_NUMBER() OVER (PARTITION BY route_id, direction ORDER BY seq)
FROM first_visit;

COMMIT;

-- Quick check
SELECT 'route' AS tbl, COUNT(*) FROM route UNION ALL
SELECT 'station', COUNT(*) FROM station UNION ALL
SELECT 'service_calendar', COUNT(*) FROM service_calendar UNION ALL
SELECT 'trip', COUNT(*) FROM trip UNION ALL
SELECT 'stop_time', COUNT(*) FROM stop_time UNION ALL
SELECT 'serves', COUNT(*) FROM serves UNION ALL
SELECT 'transfers_to', COUNT(*) FROM transfers_to;
