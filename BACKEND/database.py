import sqlite3

DB_PATH = "weatherguard.db"

# An anomaly is considered "active" on the live dashboard
# if it was generated within this time window.
ACTIVE_ALERT_WINDOW_MINUTES = 30


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT,
            timestamp TEXT,
            temperature_c REAL,
            relative_humidity_pct REAL,
            pressure_hpa REAL,
            anomaly INTEGER,
            anomaly_score REAL,
            weather_or_sensor TEXT,
            confidence REAL,
            fault_component TEXT,
            evidence_temporal REAL,
            evidence_spatial REAL,
            evidence_multivariate REAL
        )
    """)

    conn.commit()
    conn.close()

    print("Database initialized. Table 'readings' ready.")


def insert_reading(data: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO readings (
            station_id,
            timestamp,
            temperature_c,
            relative_humidity_pct,
            pressure_hpa,
            anomaly,
            anomaly_score,
            weather_or_sensor,
            confidence,
            fault_component,
            evidence_temporal,
            evidence_spatial,
            evidence_multivariate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["station_id"],
        data["timestamp"],
        data["temperature_c"],
        data["relative_humidity_pct"],
        data["pressure_hpa"],
        int(data["anomaly"]),
        data["anomaly_score"],
        data["weather_or_sensor"],
        data.get("confidence"),
        data["fault_component"],
        data["evidence"]["temporal"],
        data["evidence"]["spatial"],
        data["evidence"]["multivariate"]
    ))

    conn.commit()
    conn.close()


def get_latest_per_station():
    """
    Returns the latest stored telemetry result for every AWS station.

    This intentionally uses the latest database record and is independent
    of the active-alert time window.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.*
        FROM readings r
        INNER JOIN (
            SELECT station_id, MAX(id) AS max_id
            FROM readings
            GROUP BY station_id
        ) latest
        ON r.station_id = latest.station_id
        AND r.id = latest.max_id
    """)

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()
    return rows


def get_recent_alerts(limit=50):
    """
    Returns ONLY currently active/recent anomaly records.

    Historical benchmark anomalies remain in the database, but they are
    not treated as active alerts once they are older than the configured
    live-alert window.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM readings
        WHERE anomaly = 1
          AND datetime(timestamp) >= datetime(
              'now',
              ?
          )
        ORDER BY id DESC
        LIMIT ?
    """, (
        f"-{ACTIVE_ALERT_WINDOW_MINUTES} minutes",
        limit
    ))

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()
    return rows


def get_station_history(station_id, limit=50):
    """
    Returns historical readings for a station.

    This is deliberately NOT restricted by the active-alert window because
    the frontend uses this endpoint for the 1h / 6h / 24h / 7d telemetry
    graphs.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM readings
        WHERE station_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (
        station_id,
        limit
    ))

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()
    return rows


def reset_database():
    """
    Full database reset.

    WARNING:
    This clears benchmark history as well as live data.
    Use presentation_reset.py instead when preparing for the demo.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM readings")

    conn.commit()
    conn.close()

    print("Database reset — all readings cleared.")