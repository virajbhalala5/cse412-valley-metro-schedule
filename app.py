"""Valley Metro Light Rail Schedule app - CSE 412 Phase 3, Group 23.
Flask web app on top of the Phase 2 PostgreSQL database `transit`."""
import os
import re
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

import psycopg
from psycopg.rows import dict_row
from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for, abort)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DB_URL = os.environ.get("DATABASE_URL", "dbname=transit")

DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


# ---------- database helpers ----------
def db():
    if "db" not in g:
        g.db = psycopg.connect(DB_URL, row_factory=dict_row)
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def q(sql, params=None):
    with db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall() if cur.description else []


def q1(sql, params=None):
    rows = q(sql, params)
    return rows[0] if rows else None


def run(sql, params=None):
    with db().cursor() as cur:
        cur.execute(sql, params or ())


def init_users():
    """Create the app_user table and a demo admin the first time the app starts."""
    with psycopg.connect(DB_URL) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS app_user (
            username VARCHAR(30) PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role VARCHAR(10) NOT NULL DEFAULT 'admin')""")
        n = conn.execute("SELECT COUNT(*) FROM app_user").fetchone()[0]
        if n == 0:
            conn.execute("INSERT INTO app_user VALUES (%s,%s,'admin')",
                         ("admin", generate_password_hash("admin123")))


# ---------- formatting ----------
def hhmm(td):
    """Interval -> 'HH:MM'. GTFS times past 24:00 are shown as 25:10 etc."""
    if td is None:
        return ""
    s = int(td.total_seconds())
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"


app.jinja_env.filters["hhmm"] = hhmm


def to_interval(text):
    if not TIME_RE.match(text or ""):
        raise ValueError(f"'{text}' is not a time like 08:30")
    h, m = text.split(":")
    if int(m) > 59:
        raise ValueError(f"'{text}' has invalid minutes")
    return timedelta(hours=int(h), minutes=int(m))


def day_flag(day):
    """SQL expression: is service_calendar c running on the given date?"""
    cases = " ".join(f"WHEN {i} THEN c.{d}" for i, d in enumerate(DAYS))
    return (f"(CASE EXTRACT(dow FROM %s::date) {cases} END "
            f"AND %s::date BETWEEN c.start_date AND c.end_date)")


def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


# ---------- auth ----------
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user" not in session:
            flash("Please log in to change the schedule.", "warn")
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


@app.before_request
def csrf_check():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        abort(400, "Bad form token")


@app.context_processor
def inject():
    return {"csrf": session.get("csrf", ""), "user": session.get("user")}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = q1("SELECT * FROM app_user WHERE username=%s", (request.form["username"],))
        if row and check_password_hash(row["password_hash"], request.form["password"]):
            session["user"] = row["username"]
            flash("Logged in.", "ok")
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("home"))
        flash("Wrong username or password.", "err")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    flash("Logged out.", "ok")
    return redirect(url_for("home"))


# ---------- pages: read ----------
@app.route("/")
def home():
    counts = q1("""SELECT (SELECT COUNT(*) FROM route) routes,
                          (SELECT COUNT(*) FROM station) stations,
                          (SELECT COUNT(*) FROM trip) trips,
                          (SELECT COUNT(*) FROM stop_time) stop_times""")
    routes = q("SELECT * FROM route ORDER BY short_name")
    return render_template("home.html", counts=counts, routes=routes, mapdata=map_data())


@app.route("/departures")
def departures():
    stations = q("SELECT station_id, name FROM station ORDER BY name")
    station_id = request.args.get("station", "")
    day = parse_date(request.args.get("date", "")) or date.today()
    t = request.args.get("time", "08:00")
    rows, error, station = [], None, None
    if station_id:
        try:
            t_iv = to_interval(t)
            station = q1("SELECT name FROM station WHERE station_id=%s", (station_id,))
            rows = q(f"""
                SELECT r.short_name AS line, r.color, tr.headsign, st.departure_time
                FROM stop_time st
                JOIN trip tr ON tr.trip_id = st.trip_id
                JOIN route r ON r.route_id = tr.route_id
                JOIN service_calendar c ON c.service_id = tr.service_id
                WHERE st.station_id = %s AND {day_flag(day)}
                  AND st.departure_time >= %s
                ORDER BY st.departure_time LIMIT 10""",
                (station_id, day, day, t_iv))
        except ValueError as e:
            error = str(e)
    return render_template("departures.html", stations=stations, station_id=station_id,
                           day=day, t=t, rows=rows, error=error, station=station)


@app.route("/summary")
def summary():
    day = parse_date(request.args.get("date", "")) or date.today()
    rows = q(f"""
        SELECT r.short_name AS line, r.long_name, r.color,
               COUNT(DISTINCT t.trip_id) AS trips,
               COUNT(DISTINCT st.station_id) AS stations,
               MIN(st.departure_time) AS first_dep,
               MAX(st.departure_time) AS last_dep
        FROM route r
        JOIN trip t ON t.route_id = r.route_id
        JOIN service_calendar c ON c.service_id = t.service_id
        JOIN stop_time st ON st.trip_id = t.trip_id
        WHERE {day_flag(day)}
        GROUP BY r.route_id, r.short_name, r.long_name, r.color
        ORDER BY trips DESC""", (day, day))
    return render_template("summary.html", rows=rows, day=day)


@app.route("/stations")
def stations():
    term = request.args.get("q", "").strip()
    rows = q("""SELECT s.station_id, s.name, s.zone_id,
                       COALESCE(string_agg(DISTINCT r.short_name, ', ' ORDER BY r.short_name), '') AS lines
                FROM station s
                LEFT JOIN serves sv ON sv.station_id = s.station_id
                LEFT JOIN route r ON r.route_id = sv.route_id
                WHERE s.name ILIKE %s
                GROUP BY s.station_id ORDER BY s.name""", (f"%{term}%",))
    colors = {r["short_name"]: r["color"] for r in q("SELECT short_name, color FROM route")}
    return render_template("stations.html", rows=rows, term=term, colors=colors)


@app.route("/trips")
def trips():
    route = request.args.get("route", "")
    term = request.args.get("q", "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per = 25
    where, params = ["(t.headsign ILIKE %s OR t.trip_id ILIKE %s)"], [f"%{term}%"] * 2
    if route:
        where.append("t.route_id = %s")
        params.append(route)
    w = " AND ".join(where)
    total = q1(f"SELECT COUNT(*) n FROM trip t WHERE {w}", params)["n"]
    rows = q(f"""SELECT t.trip_id, t.direction, t.headsign, t.service_id, r.short_name, r.color,
                        (SELECT MIN(departure_time) FROM stop_time s WHERE s.trip_id = t.trip_id) AS start_time
                 FROM trip t JOIN route r ON r.route_id = t.route_id
                 WHERE {w} ORDER BY t.trip_id LIMIT %s OFFSET %s""",
             params + [per, (page - 1) * per])
    routes = q("SELECT route_id, short_name FROM route ORDER BY short_name")
    return render_template("trips.html", rows=rows, routes=routes, route=route, term=term,
                           page=page, pages=max((total + per - 1) // per, 1), total=total)


@app.route("/trips/<trip_id>")
def trip_detail(trip_id):
    trip = q1("""SELECT t.*, r.short_name, r.long_name, r.color FROM trip t
                 JOIN route r ON r.route_id=t.route_id WHERE trip_id=%s""", (trip_id,))
    if not trip:
        abort(404)
    stops = q("""SELECT st.*, s.name FROM stop_time st JOIN station s ON s.station_id=st.station_id
                 WHERE trip_id=%s ORDER BY stop_sequence""", (trip_id,))
    return render_template("trip_detail.html", trip=trip, stops=stops)


# ---------- pages: write (login required) ----------
def form_data():
    routes = q("SELECT route_id, short_name, long_name FROM route ORDER BY short_name")
    services = q("SELECT service_id FROM service_calendar ORDER BY service_id")
    stations = q("SELECT station_id, name FROM station ORDER BY name")
    return routes, services, stations


def read_stops(form):
    """Read repeated stop rows (station / arrive / depart) from the form."""
    sts, arr, dep = (form.getlist(k) for k in ("station", "arrive", "depart"))
    out = []
    for i, (s, a, d) in enumerate(zip(sts, arr, dep), start=1):
        if not s and not a and not d:
            continue
        out.append((len(out) + 1, s, to_interval(a), to_interval(d)))
    return out


@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def trip_new():
    routes, services, stations = form_data()
    if request.method == "POST":
        f = request.form
        try:
            stops = read_stops(f)
            if len(stops) < 2:
                raise ValueError("A trip needs at least 2 stops.")
            run("INSERT INTO trip (trip_id, route_id, service_id, direction, headsign) "
                "VALUES (%s,%s,%s,%s,%s)",
                (f["trip_id"].strip(), f["route_id"], f["service_id"],
                 int(f["direction"]), f["headsign"].strip() or None))
            for seq, s, a, d in stops:
                run("INSERT INTO stop_time VALUES (%s,%s,%s,%s,%s)",
                    (f["trip_id"].strip(), seq, s, a, d))
            db().commit()
            flash(f"Trip {f['trip_id']} added with {len(stops)} stops.", "ok")
            return redirect(url_for("trip_detail", trip_id=f["trip_id"].strip()))
        except (ValueError, psycopg.Error) as e:
            db().rollback()
            flash(f"Could not add trip: {getattr(e, 'diag', None) and e.diag.message_primary or e}", "err")
    return render_template("trip_form.html", mode="new", routes=routes, services=services,
                           stations=stations, trip=request.form, stops=[])


@app.route("/trips/<trip_id>/edit", methods=["GET", "POST"])
@login_required
def trip_edit(trip_id):
    trip = q1("SELECT * FROM trip WHERE trip_id=%s", (trip_id,))
    if not trip:
        abort(404)
    routes, services, stations = form_data()
    if request.method == "POST":
        f = request.form
        try:
            run("UPDATE trip SET headsign=%s, service_id=%s WHERE trip_id=%s",
                (f["headsign"].strip() or None, f["service_id"], trip_id))
            shift = int(f.get("shift_minutes") or 0)
            if shift:
                run("""UPDATE stop_time SET arrival_time = arrival_time + make_interval(mins => %s),
                       departure_time = departure_time + make_interval(mins => %s)
                       WHERE trip_id=%s""", (shift, shift, trip_id))
            db().commit()
            flash("Trip updated" + (f" (all stops shifted {shift:+d} min)." if shift else "."), "ok")
            return redirect(url_for("trip_detail", trip_id=trip_id))
        except (ValueError, psycopg.Error) as e:
            db().rollback()
            flash(f"Could not update trip: {getattr(e, 'diag', None) and e.diag.message_primary or e}", "err")
    stops = q("""SELECT st.*, s.name FROM stop_time st JOIN station s ON s.station_id=st.station_id
                 WHERE trip_id=%s ORDER BY stop_sequence""", (trip_id,))
    return render_template("trip_form.html", mode="edit", routes=routes, services=services,
                           stations=stations, trip=trip, stops=stops)


@app.route("/trips/<trip_id>/stop/<int:seq>", methods=["POST"])
@login_required
def stop_update(trip_id, seq):
    try:
        a, d = to_interval(request.form["arrive"]), to_interval(request.form["depart"])
        run("UPDATE stop_time SET arrival_time=%s, departure_time=%s WHERE trip_id=%s AND stop_sequence=%s",
            (a, d, trip_id, seq))
        db().commit()
        flash(f"Stop {seq} updated.", "ok")
    except (ValueError, psycopg.Error) as e:
        db().rollback()
        flash(f"Could not update stop: {getattr(e, 'diag', None) and e.diag.message_primary or e}", "err")
    return redirect(url_for("trip_edit", trip_id=trip_id))


@app.route("/trips/<trip_id>/delete", methods=["POST"])
@login_required
def trip_delete(trip_id):
    n = q1("SELECT COUNT(*) n FROM stop_time WHERE trip_id=%s", (trip_id,))["n"]
    run("DELETE FROM trip WHERE trip_id=%s", (trip_id,))   # stop_time rows go via ON DELETE CASCADE
    db().commit()
    flash(f"Trip {trip_id} deleted (and its {n} stop times).", "ok")
    return redirect(url_for("trips"))


# ---------- new: map, planner, station detail ----------
def next_departures(station_id, day, t_iv, limit=8):
    return q(f"""
        SELECT r.short_name AS line, r.color, tr.headsign, tr.trip_id, st.departure_time
        FROM stop_time st
        JOIN trip tr ON tr.trip_id = st.trip_id
        JOIN route r ON r.route_id = tr.route_id
        JOIN service_calendar c ON c.service_id = tr.service_id
        WHERE st.station_id = %s AND {day_flag(day)} AND st.departure_time >= %s
        ORDER BY st.departure_time LIMIT %s""", (station_id, day, day, t_iv, limit))


@app.route("/map-data")
def map_data():
    """Everything the interactive line map needs, built from station and serves."""
    stations = q("""SELECT s.station_id AS id, s.name, s.latitude::float AS lat, s.longitude::float AS lon,
                           COALESCE(array_agg(DISTINCT r.short_name) FILTER (WHERE r.short_name IS NOT NULL), '{}') AS lines
                    FROM station s LEFT JOIN serves sv ON sv.station_id = s.station_id
                    LEFT JOIN route r ON r.route_id = sv.route_id GROUP BY s.station_id""")
    rows = q("""SELECT r.route_id, r.short_name, r.color, sv.direction, sv.station_id
                FROM serves sv JOIN route r ON r.route_id = sv.route_id
                ORDER BY r.route_id, sv.direction, sv.stop_order""")
    lines = {}   # one drawn path per route and direction (the streetcar uses different streets each way)
    for r in rows:
        ln = lines.setdefault((r["route_id"], r["direction"]),
                              {"name": r["short_name"], "color": r["color"], "stops": []})
        ln["stops"].append(r["station_id"])
    return {"stations": stations, "lines": list(lines.values())}


@app.route("/api/station/<station_id>/next")
def api_station_next(station_id):
    st = q1("SELECT station_id, name FROM station WHERE station_id=%s", (station_id,))
    if not st:
        abort(404)
    now = datetime.now()
    t_iv = timedelta(hours=now.hour, minutes=now.minute)
    deps = next_departures(station_id, date.today(), t_iv, 5)
    note = "from now"
    if not deps:                                   # nothing left today: show the first trains of the day
        deps = next_departures(station_id, date.today(), timedelta(0), 5)
        note = "first trains today"
    lines = q("""SELECT DISTINCT r.short_name, r.color FROM serves sv JOIN route r ON r.route_id=sv.route_id
                 WHERE sv.station_id=%s ORDER BY r.short_name""", (station_id,))
    return {"id": st["station_id"], "name": st["name"], "note": note,
            "lines": [{"name": l["short_name"], "color": l["color"]} for l in lines],
            "deps": [{"time": hhmm(d["departure_time"]), "line": d["line"], "color": d["color"], "toward": d["headsign"]} for d in deps]}


@app.route("/planner")
def planner():
    stations = q("SELECT station_id, name FROM station ORDER BY name")
    a, b = request.args.get("from", ""), request.args.get("to", "")
    day = parse_date(request.args.get("date", "")) or date.today()
    t = request.args.get("time", "08:00")
    rows, error, names = [], None, {}
    if a and b:
        if a == b:
            error = "Pick two different stations."
        else:
            try:
                t_iv = to_interval(t)
                names = {r["station_id"]: r["name"] for r in stations if r["station_id"] in (a, b)}
                rows = q(f"""
                    SELECT r.short_name AS line, r.color, tr.headsign, tr.trip_id,
                           x.departure_time AS leaves, y.arrival_time AS arrives,
                           (y.stop_sequence - x.stop_sequence) AS stops_between
                    FROM stop_time x
                    JOIN stop_time y ON y.trip_id = x.trip_id AND y.stop_sequence > x.stop_sequence
                    JOIN trip tr ON tr.trip_id = x.trip_id
                    JOIN route r ON r.route_id = tr.route_id
                    JOIN service_calendar c ON c.service_id = tr.service_id
                    WHERE x.station_id = %s AND y.station_id = %s AND {day_flag(day)}
                      AND x.departure_time >= %s
                    ORDER BY x.departure_time LIMIT 8""", (a, b, day, day, t_iv))
            except ValueError as e:
                error = str(e)
    return render_template("planner.html", stations=stations, a=a, b=b, day=day, t=t,
                           rows=rows, error=error, names=names)


@app.route("/stations/<station_id>")
def station_detail(station_id):
    st = q1("SELECT * FROM station WHERE station_id=%s", (station_id,))
    if not st:
        abort(404)
    day = parse_date(request.args.get("date", "")) or date.today()
    t = request.args.get("time", "08:00")
    try:
        t_iv = to_interval(t)
    except ValueError:
        t, t_iv = "08:00", timedelta(hours=8)
    lines = q("""SELECT DISTINCT r.short_name, r.color, r.long_name FROM serves sv
                 JOIN route r ON r.route_id=sv.route_id WHERE sv.station_id=%s ORDER BY r.short_name""", (station_id,))
    transfers = q("""SELECT s.station_id, s.name, tt.min_transfer_seconds FROM transfers_to tt
                     JOIN station s ON s.station_id = tt.to_station_id
                     WHERE tt.from_station_id=%s ORDER BY tt.min_transfer_seconds""", (station_id,))
    deps = next_departures(station_id, day, t_iv, 8)
    return render_template("station_detail.html", st=st, lines=lines, transfers=transfers,
                           deps=deps, day=day, t=t)


init_users()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
