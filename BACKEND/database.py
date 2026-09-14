import os

import psycopg
from psycopg.rows import dict_row


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set."
    )


# ============================================================
# CONNECTION
# ============================================================

def get_connection():
    """
    Open a PostgreSQL connection.

    DATABASE_URL is supplied through the environment so
    credentials are never hardcoded into the source code.
    """

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():
    """
    Create the readings table and required indexes.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS readings (
                    id BIGSERIAL PRIMARY KEY,

                    station_id TEXT NOT NULL,

                    timestamp TIMESTAMPTZ NOT NULL,

                    temperature_c DOUBLE PRECISION,
                    relative_humidity_pct DOUBLE PRECISION,
                    pressure_hpa DOUBLE PRECISION,

                    anomaly INTEGER NOT NULL DEFAULT 0,

                    anomaly_score DOUBLE PRECISION,

                    weather_or_sensor TEXT,

                    confidence DOUBLE PRECISION,

                    fault_component TEXT,

                    evidence_temporal DOUBLE PRECISION,
                    evidence_spatial DOUBLE PRECISION,
                    evidence_multivariate DOUBLE PRECISION,

                    source TEXT NOT NULL DEFAULT 'legacy'
                )
            """)

            # ------------------------------------------------
            # Live station lookup
            # ------------------------------------------------

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_readings_live_station_time
                ON readings (
                    source,
                    station_id,
                    timestamp DESC,
                    id DESC
                )
            """)

            # ------------------------------------------------
            # Alert lookup
            # ------------------------------------------------

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_readings_live_alerts
                ON readings (
                    source,
                    anomaly,
                    timestamp DESC,
                    id DESC
                )
            """)

            # ------------------------------------------------
            # General timestamp lookup
            # ------------------------------------------------

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_readings_timestamp
                ON readings (
                    timestamp DESC
                )
            """)

        conn.commit()

    print(
        "PostgreSQL database initialized. "
        "Table 'readings' ready."
    )


# ============================================================
# INSERT READING
# ============================================================

def insert_reading(
    data: dict,
    source: str = "live",
):
    """
    Insert one processed telemetry result.

    Supported sources:

        historical
        demo
        live
        legacy
    """

    allowed_sources = {
        "historical",
        "demo",
        "live",
        "legacy",
    }

    if source not in allowed_sources:
        raise ValueError(
            f"Invalid reading source: {source}"
        )

    with get_connection() as conn:

        with conn.cursor() as cur:

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
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
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
                data.get("evidence", {}).get("temporal"),
                data.get("evidence", {}).get("spatial"),
                data.get("evidence", {}).get("multivariate"),
                source,
            ))

        conn.commit()


# ============================================================
# LATEST LIVE READING PER STATION
# ============================================================

def get_latest_per_station():
    """
    Return the latest LIVE telemetry result for every station.

    Historical and Demo Center records are deliberately
    excluded from live station state.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT DISTINCT ON (station_id)
                    *
                FROM readings
                WHERE source = 'live'
                ORDER BY
                    station_id,
                    timestamp DESC,
                    id DESC
            """)

            return cur.fetchall()


# ============================================================
# RECENT LIVE ALERTS
# ============================================================

def get_recent_alerts(
    limit=50,
):
    """
    Return only LIVE anomaly records.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT *
                FROM readings
                WHERE source = 'live'
                  AND anomaly = 1
                ORDER BY
                    timestamp DESC,
                    id DESC
                LIMIT %s
            """, (
                limit,
            ))

            return cur.fetchall()


# ============================================================
# LIVE STATION HISTORY
# ============================================================

def get_station_history(
    station_id,
    limit=50,
):
    """
    Return the newest LIVE readings for a station,
    chronologically ordered for dashboard plotting.

    Important:
    We first select the newest N records and then reorder
    them oldest -> newest for the frontend graph.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT *
                FROM (
                    SELECT *
                    FROM readings
                    WHERE station_id = %s
                      AND source = 'live'
                    ORDER BY
                        timestamp DESC,
                        id DESC
                    LIMIT %s
                ) q
                ORDER BY
                    timestamp ASC,
                    id ASC
            """, (
                station_id,
                limit,
            ))

            return cur.fetchall()


# ============================================================
# FEATURE-ENGINEERING HISTORY
# ============================================================

def get_station_feature_history(
    station_id,
    before_timestamp=None,
    limit=96,
):
    """
    Return raw telemetry history required by the feature engine.

    The ML state uses:

        historical
        live

    Demo records are deliberately excluded so Demo Center
    experiments cannot contaminate the real-time state.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            if before_timestamp is None:

                cur.execute("""
                    SELECT
                        station_id,
                        timestamp,
                        temperature_c,
                        relative_humidity_pct,
                        pressure_hpa
                    FROM readings
                    WHERE station_id = %s
                      AND source IN (
                          'historical',
                          'live'
                      )
                    ORDER BY
                        timestamp DESC,
                        id DESC
                    LIMIT %s
                """, (
                    station_id,
                    limit,
                ))

            else:

                cur.execute("""
                    SELECT
                        station_id,
                        timestamp,
                        temperature_c,
                        relative_humidity_pct,
                        pressure_hpa
                    FROM readings
                    WHERE station_id = %s
                      AND source IN (
                          'historical',
                          'live'
                      )
                      AND timestamp < %s
                    ORDER BY
                        timestamp DESC,
                        id DESC
                    LIMIT %s
                """, (
                    station_id,
                    before_timestamp,
                    limit,
                ))

            rows = cur.fetchall()

            # Feature engine expects chronological history.
            rows.reverse()

            return rows


# ============================================================
# SPATIAL CONTEXT
# ============================================================

def get_latest_station_context(
    timestamp,
    max_age_seconds=1800,
):
    """
    Return readings from all stations at the exact supplied
    timestamp.

    Spatial features must compare contemporaneous observations.
    A reading from an earlier or later timestamp must not be used
    as a substitute for the requested observation.

    Demo data is excluded.

    max_age_seconds is retained in the function signature for
    compatibility with existing callers.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    station_id,
                    timestamp,
                    temperature_c,
                    relative_humidity_pct,
                    pressure_hpa
                FROM readings
                WHERE source IN (
                    'historical',
                    'live'
                )
                  AND timestamp = %s
                ORDER BY station_id
            """, (
                timestamp,
            ))

            return cur.fetchall()


# ============================================================
# LIVE DATA RESET
# ============================================================

def reset_live_data():
    """
    Delete ONLY live telemetry.

    Historical benchmark data and Demo Center data remain
    untouched.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                DELETE FROM readings
                WHERE source = 'live'
            """)

            deleted = cur.rowcount

        conn.commit()

    print(
        f"Live data reset — {deleted} readings removed."
    )


# ============================================================
# FULL DATABASE RESET
# ============================================================

def reset_database():
    """
    Full development reset.

    Deletes every reading regardless of source.

    This is retained for compatibility with the existing
    /reset endpoint.

    Presentation/demo reset should use reset_live_data()
    instead.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                DELETE FROM readings
            """)

            deleted = cur.rowcount

        conn.commit()

    print(
        f"Database reset — {deleted} readings removed."
    )