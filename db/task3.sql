-- CSE 412 Phase 2, Task 3: SQL queries and CRUD operations (Group 23)
-- Run after schema.sql and load.sql.   psql -d transit -f task3.sql
\pset pager off

-- ============================================================
-- SELECT 1: join + filter  (rider question: "when is the next train?")
-- Next 6 departures after 8:00 AM from Downtown Phx Hub/Jefferson St
-- on Monday, 9 Nov 2026, with route, direction and destination.
-- ============================================================
SELECT r.short_name AS line,
       t.headsign   AS toward,
       st.departure_time AS departs
FROM stop_time st
JOIN trip t             ON t.trip_id = st.trip_id
JOIN route r            ON r.route_id = t.route_id
JOIN service_calendar c ON c.service_id = t.service_id
JOIN station s          ON s.station_id = st.station_id
WHERE s.name = 'Downtown Phx Hub/Jefferson St'
  AND c.monday
  AND DATE '2026-11-09' BETWEEN c.start_date AND c.end_date
  AND st.departure_time >= INTERVAL '08:00:00'
ORDER BY st.departure_time
LIMIT 6;

-- ============================================================
-- SELECT 2: aggregation  (planner question: "how much service does each line run?")
-- For each line on a Monday: number of trips, stations served, and
-- the first and last departure of the day (times past 24:00 are after midnight).
-- ============================================================
SELECT r.short_name AS line,
       COUNT(DISTINCT t.trip_id)    AS weekday_trips,
       COUNT(DISTINCT st.station_id) AS stations_served,
       MIN(st.departure_time)       AS first_departure,
       MAX(st.departure_time)       AS last_departure
FROM route r
JOIN trip t             ON t.route_id = r.route_id
JOIN service_calendar c ON c.service_id = t.service_id
JOIN stop_time st       ON st.trip_id = t.trip_id
WHERE c.monday
  AND DATE '2026-11-09' BETWEEN c.start_date AND c.end_date
GROUP BY r.route_id, r.short_name
ORDER BY weekday_trips DESC;

-- ============================================================
-- INSERT: add a new service day.
-- Create a holiday calendar (runs like Sunday) and one trip on it.
-- ============================================================
INSERT INTO service_calendar
  (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
VALUES
  ('A_Holiday_2026', false, false, false, false, false, false, true, '2026-11-26', '2026-11-26');

INSERT INTO trip (trip_id, route_id, service_id, direction, headsign)
VALUES ('HOL-0001', 'A', 'A_Holiday_2026', 0, 'Gilbert Rd/Main St');

INSERT INTO stop_time (trip_id, stop_sequence, station_id, arrival_time, departure_time)
VALUES ('HOL-0001', 1, '9055', INTERVAL '09:00:00', INTERVAL '09:00:00'),
       ('HOL-0001', 2, '9053', INTERVAL '09:04:00', INTERVAL '09:05:00');

SELECT t.trip_id, t.route_id, t.service_id, st.stop_sequence, st.station_id, st.departure_time
FROM trip t JOIN stop_time st USING (trip_id)
WHERE t.trip_id = 'HOL-0001'
ORDER BY st.stop_sequence;

-- ============================================================
-- UPDATE: a schedule change.
-- Shift the holiday trip's second stop 3 minutes later and rename its headsign.
-- ============================================================
UPDATE stop_time
SET arrival_time   = arrival_time   + INTERVAL '3 minutes',
    departure_time = departure_time + INTERVAL '3 minutes'
WHERE trip_id = 'HOL-0001' AND stop_sequence = 2;

UPDATE trip
SET headsign = 'Gilbert Rd/Main St (Holiday)'
WHERE trip_id = 'HOL-0001';

SELECT t.headsign, st.stop_sequence, st.arrival_time, st.departure_time
FROM trip t JOIN stop_time st USING (trip_id)
WHERE t.trip_id = 'HOL-0001'
ORDER BY st.stop_sequence;

-- ============================================================
-- DELETE: cancel the holiday trip.
-- stop_time rows go with it because of ON DELETE CASCADE.
-- ============================================================
SELECT COUNT(*) AS stop_times_before FROM stop_time WHERE trip_id = 'HOL-0001';

DELETE FROM trip WHERE trip_id = 'HOL-0001';

SELECT (SELECT COUNT(*) FROM trip      WHERE trip_id = 'HOL-0001') AS trips_after,
       (SELECT COUNT(*) FROM stop_time WHERE trip_id = 'HOL-0001') AS stop_times_after;

-- Clean-up: remove the holiday calendar so the database is back to its original
-- state and this script can be run again.
DELETE FROM service_calendar WHERE service_id = 'A_Holiday_2026';
