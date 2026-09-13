import sqlite3

DB_PATH = "weatherguard.db"

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
            evidence_multivariate REAL,
            source TEXT NOT NULL DEFAULT 'legacy'
        )
    """)

    # --------------------------------------------------------
    # Migrate an older database that does not have source.
    # --------------------------------------------------------

    columns = {
        row[1]
        for row in cur.execute(
            "PRAGMA table_info(readings)"
        ).fetchall()
    }

    if "source" not in columns:
        cur.execute("""
            ALTER TABLE readings
            ADD COLUMN source TEXT NOT NULL DEFAULT 'legacy'
        """)

    conn.commit()
    conn.close()

    print("Database initialized. Table 'readings' ready.")


def insert_reading(data: dict, source: str = "live"):
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
            evidence_multivariate,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data["evidence"]["multivariate"],
        source,
    ))

    conn.commit()
    conn.close()


def get_latest_per_station():
    """
    Returns the latest LIVE telemetry result for every station.

    Historical benchmark data and Demo Center results are deliberately
    excluded from the live station state.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.*
        FROM readings r
        INNER JOIN (
            SELECT station_id, MAX(id) AS max_id
            FROM readings
            WHERE source = 'live'
            GROUP BY station_id
        ) latest
        ON r.station_id = latest.station_id
        AND r.id = latest.max_id
        WHERE r.source = 'live'
    """)

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()
    return rows


def get_recent_alerts(limit=50):
    """
    Returns only LIVE anomaly records.

    Historical benchmark anomalies and Demo Center results do not
    appear as active live alerts.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM readings
        WHERE source = 'live'
          AND anomaly = 1
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()
    return rows


def get_station_history(station_id, limit=50):
    """
    Returns ONLY LIVE telemetry for the live dashboard graph.

    Historical benchmark telemetry remains safely stored in the
    database, but is not mixed into the live graph.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM readings
        WHERE station_id = ?
          AND source = 'live'
        ORDER BY datetime(timestamp) ASC, id ASC
        LIMIT ?
    """, (
        station_id,
        limit,
    ))

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()
    return rows


def reset_database():
    """
    Full database reset.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM readings")

    conn.commit()
    conn.close()

    print("Database reset — all readings cleared.")