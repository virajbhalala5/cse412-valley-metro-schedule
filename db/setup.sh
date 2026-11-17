#!/usr/bin/env bash
# Creates the `transit` database, the tables, and loads the Valley Metro data.
# Usage:  ./db/setup.sh [database_name]     (default: transit)
set -e
DB="${1:-transit}"
HERE="$(cd "$(dirname "$0")" && pwd)"
createdb "$DB" 2>/dev/null || echo "(database $DB already exists, reusing it)"
psql -d "$DB" -v ON_ERROR_STOP=1 -q -f "$HERE/schema.sql"
cd "$HERE/data" && psql -d "$DB" -v ON_ERROR_STOP=1 -q -f "$HERE/load.sql"
psql -d "$DB" -c "SELECT (SELECT count(*) FROM route) routes, (SELECT count(*) FROM station) stations, (SELECT count(*) FROM trip) trips, (SELECT count(*) FROM stop_time) stop_times"
