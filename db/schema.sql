-- CSE 412 Phase 2 - Group 23 - Transit Schedule System
-- ER-to-relational schema (PostgreSQL). Run with:  psql -d transit -f schema.sql

DROP TABLE IF EXISTS route_shape, transfers_to, serves, stop_time, trip, service_calendar, station, route CASCADE;

-- Entity set Route
CREATE TABLE route (
    route_id    VARCHAR(20)  PRIMARY KEY,
    short_name  VARCHAR(20),
    long_name   VARCHAR(100),
    mode        VARCHAR(20)  NOT NULL DEFAULT 'rail',
    color       CHAR(6)      CHECK (color ~ '^[0-9A-Fa-f]{6}$'),
    CONSTRAINT route_has_name CHECK (short_name IS NOT NULL OR long_name IS NOT NULL)
);

-- Entity set Station
CREATE TABLE station (
    station_id  VARCHAR(20)  PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    latitude    NUMERIC(9,6) NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude   NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    zone_id     VARCHAR(20)
);

-- Entity set ServiceCalendar (days_of_week stored as one flag per day)
CREATE TABLE service_calendar (
    service_id  VARCHAR(40)  PRIMARY KEY,
    monday      BOOLEAN NOT NULL,
    tuesday     BOOLEAN NOT NULL,
    wednesday   BOOLEAN NOT NULL,
    thursday    BOOLEAN NOT NULL,
    friday      BOOLEAN NOT NULL,
    saturday    BOOLEAN NOT NULL,
    sunday      BOOLEAN NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    CONSTRAINT calendar_dates_ordered CHECK (end_date >= start_date)
);

-- Entity set Trip. Operates (Route-Trip) and Govern (ServiceCalendar-Trip) are
-- one-to-many with total participation of Trip, so they become NOT NULL foreign keys.
CREATE TABLE trip (
    trip_id     VARCHAR(60)  PRIMARY KEY,
    route_id    VARCHAR(20)  NOT NULL REFERENCES route(route_id),
    service_id  VARCHAR(40)  NOT NULL REFERENCES service_calendar(service_id),
    direction   SMALLINT     NOT NULL CHECK (direction IN (0, 1)),
    headsign    VARCHAR(100)
);

-- Weak entity set StopTime, identified by its owning Trip (Has) plus stop_sequence.
-- At (StopTime-Station) is many-to-one with total participation, so station_id is NOT NULL.
CREATE TABLE stop_time (
    trip_id         VARCHAR(60) NOT NULL REFERENCES trip(trip_id) ON DELETE CASCADE,
    stop_sequence   INTEGER     NOT NULL CHECK (stop_sequence > 0),
    station_id      VARCHAR(20) NOT NULL REFERENCES station(station_id),
    arrival_time    INTERVAL    NOT NULL,   -- INTERVAL because GTFS times can pass 24:00:00
    departure_time  INTERVAL    NOT NULL,
    PRIMARY KEY (trip_id, stop_sequence),
    CONSTRAINT arrival_not_after_departure CHECK (arrival_time <= departure_time)
);

-- Relationship set Serves (Route-Station, many-to-many) with attributes stop_order, direction
CREATE TABLE serves (
    route_id    VARCHAR(20) NOT NULL REFERENCES route(route_id)     ON DELETE CASCADE,
    station_id  VARCHAR(20) NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    direction   SMALLINT    NOT NULL CHECK (direction IN (0, 1)),
    stop_order  INTEGER     NOT NULL CHECK (stop_order > 0),
    PRIMARY KEY (route_id, station_id, direction),
    CONSTRAINT one_station_per_position UNIQUE (route_id, direction, stop_order)
);

-- Recursive relationship set TransfersTo (Station-Station) with roles from / to
CREATE TABLE transfers_to (
    from_station_id      VARCHAR(20) NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    to_station_id        VARCHAR(20) NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    min_transfer_seconds INTEGER     NOT NULL CHECK (min_transfer_seconds >= 0),
    PRIMARY KEY (from_station_id, to_station_id),
    CONSTRAINT no_self_transfer CHECK (from_station_id <> to_station_id)
);

-- Indexes that back the main rider query (next departures at a station)
CREATE INDEX idx_stop_time_station_departure ON stop_time (station_id, departure_time);
CREATE INDEX idx_trip_route   ON trip (route_id);
CREATE INDEX idx_trip_service ON trip (service_id);

-- Added in Phase 3: the drawn track of each line (from the GTFS shapes file), used by the map.
CREATE TABLE route_shape (
    route_id   VARCHAR(20)  NOT NULL REFERENCES route(route_id) ON DELETE CASCADE,
    direction  SMALLINT     NOT NULL CHECK (direction IN (0, 1)),
    seq        INTEGER      NOT NULL CHECK (seq > 0),
    latitude   NUMERIC(9,6) NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude  NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    PRIMARY KEY (route_id, direction, seq)
);

-- Added in Phase 3: which lines stop at which station, taken from the real trips (used by the app).
CREATE VIEW station_line AS
SELECT DISTINCT t.route_id, st.station_id
FROM stop_time st JOIN trip t ON t.trip_id = st.trip_id;
