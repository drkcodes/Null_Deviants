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
            station_id, timestamp, temperature_c, relative_humidity_pct, pressure_hpa,
            anomaly, anomaly_score, weather_or_sensor, confidence, fault_component,
            evidence_temporal, evidence_spatial, evidence_multivariate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["station_id"], data["timestamp"], data["temperature_c"],
        data["relative_humidity_pct"], data["pressure_hpa"],
        int(data["anomaly"]), data["anomaly_score"], data["weather_or_sensor"],
        data.get("confidence"), data["fault_component"],
        data["evidence"]["temporal"], data["evidence"]["spatial"], data["evidence"]["multivariate"]
    ))
    conn.commit()
    conn.close()

def get_latest_per_station():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.* FROM readings r
        INNER JOIN (
            SELECT station_id, MAX(id) as max_id
            FROM readings
            GROUP BY station_id
        ) latest ON r.station_id = latest.station_id AND r.id = latest.max_id
    """)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return rows

def get_recent_alerts(limit=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM readings
        WHERE anomaly = 1
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return rows

def get_station_history(station_id, limit=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM readings
        WHERE station_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (station_id, limit))
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return rows

def reset_database():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM readings")
    conn.commit()
    conn.close()
    print("Database reset — all readings cleared.")

