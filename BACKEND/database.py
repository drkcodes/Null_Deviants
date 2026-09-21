import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from live_generator import load_station_profiles


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

            # ------------------------------------------------
            # Backend-owned live tick state
            # ------------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS live_state (
                    id INTEGER PRIMARY KEY,
                    last_observation_ts TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    generator_state JSONB
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS live_ticks (
                    id BIGSERIAL PRIMARY KEY,
                    observation_ts TIMESTAMPTZ NOT NULL,
                    trigger_type TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    station_count INTEGER,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    error_message TEXT
                )
            """)

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                uq_live_ticks_idempotency_key
                ON live_ticks (idempotency_key)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_live_ticks_observation_ts
                ON live_ticks (observation_ts DESC)
            """)

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_readings_live_station_timestamp_unique
                ON readings (
                    station_id,
                    timestamp
                )
                WHERE source = 'live'
            """)

        conn.commit()

    print(
        "PostgreSQL database initialized. "
        "Table 'readings' ready."
    )


# ============================================================
# LIVE TICK STATE
# ============================================================

LIVE_TICK_LOCK_KEY = 26073001


def acquire_live_tick_lock(cur):
    """Serialize all live ticks across backend instances."""
    cur.execute(
        "SELECT pg_advisory_xact_lock(%s)",
        (LIVE_TICK_LOCK_KEY,),
    )


def _live_state_from_row(row):
    if row is None:
        return None

    generator_state = row.get("generator_state")

    if generator_state is None:
        generator_state = {}

    return {
        "last_observation_ts": row["last_observation_ts"],
        "generator_state": generator_state,
    }


def _bootstrap_generator_state_from_live_rows(cur):
    """
    Bootstrap the clean generator state from calibrated station profiles.

    The live database is NOT used as the generator baseline because live
    telemetry may contain anomalies or may have been initialized from an
    older generator state.

    The logical clock remains authoritative in live_state. This function
    only provides the clean sensor state used to generate the next
    observation.
    """

    profiles = load_station_profiles()

    if len(profiles) != 20:
        raise RuntimeError(
            "Cannot bootstrap live generator state: "
            f"expected 20 calibration profiles, found {len(profiles)}."
        )

    cur.execute("""
        SELECT DISTINCT station_id
        FROM readings
        WHERE source = 'live'
    """)
    live_station_ids = {
        str(row["station_id"])
        for row in cur.fetchall()
    }

    profile_station_ids = {
        profile.station_id
        for profile in profiles
    }

    if live_station_ids and live_station_ids != profile_station_ids:
        raise RuntimeError(
            "Cannot bootstrap live generator state: "
            "live station set does not match calibration profiles."
        )

    cur.execute("""
        SELECT last_observation_ts
        FROM live_state
        WHERE id = 1
    """)
    row = cur.fetchone()

    if row is None or row["last_observation_ts"] is None:
        raise RuntimeError(
            "Cannot bootstrap live generator state: "
            "no live observation timestamp exists."
        )

    generator_state = {}

    for profile in profiles:
        generator_state[profile.station_id] = {
            "temperature_c": float(profile.temperature_mean),
            "relative_humidity_pct": float(profile.humidity_mean),
            "pressure_hpa": float(profile.pressure_mean),
        }

    return row["last_observation_ts"], generator_state


def get_or_bootstrap_live_state(cur):
    """
    Return the singleton backend-owned live clock/state.

    The actual Neon schema is:

        id
        last_observation_ts
        updated_at
        generator_state

    If generator_state is missing, it is initialized from the
    calibrated station profiles, while the logical observation
    timestamp remains authoritative in live_state.
    """

    cur.execute("""
        SELECT
            id,
            last_observation_ts,
            updated_at,
            generator_state
        FROM live_state
        WHERE id = 1
        FOR UPDATE
    """)

    row = cur.fetchone()

    if row is None:
        last_observation_ts, generator_state = (
            _bootstrap_generator_state_from_live_rows(cur)
        )

        cur.execute("""
            INSERT INTO live_state (
                id,
                last_observation_ts,
                updated_at,
                generator_state
            )
            VALUES (
                1,
                %s,
                NOW(),
                %s
            )
        """, (
            last_observation_ts,
            Jsonb(generator_state),
        ))

        return {
            "last_observation_ts": last_observation_ts,
            "generator_state": generator_state,
        }

    state = _live_state_from_row(row)

    if not state["generator_state"]:
        last_observation_ts, generator_state = (
            _bootstrap_generator_state_from_live_rows(cur)
        )

        # Keep the database clock authoritative. If it already
        # exists, only fill the missing generator state.
        state_timestamp = state["last_observation_ts"]

        if state_timestamp != last_observation_ts:
            last_observation_ts = state_timestamp

        cur.execute("""
            UPDATE live_state
            SET
                last_observation_ts = %s,
                generator_state = %s,
                updated_at = NOW()
            WHERE id = 1
        """, (
            last_observation_ts,
            Jsonb(generator_state),
        ))

        state = {
            "last_observation_ts": last_observation_ts,
            "generator_state": generator_state,
        }

    return state


def save_live_state(
    cur,
    observation_ts,
    generator_state,
):
    """Persist the clean backend-owned generator state."""

    cur.execute("""
        INSERT INTO live_state (
            id,
            last_observation_ts,
            updated_at,
            generator_state
        )
        VALUES (
            1,
            %s,
            NOW(),
            %s
        )
        ON CONFLICT (id)
        DO UPDATE SET
            last_observation_ts = EXCLUDED.last_observation_ts,
            updated_at = NOW(),
            generator_state = EXCLUDED.generator_state
    """, (
        observation_ts,
        Jsonb(generator_state),
    ))


def record_live_tick(
    cur,
    observation_ts,
    trigger_type,
    station_count,
    status="completed",
    error_message=None,
):
    """
    Record one live tick.

    The logical observation timestamp is the idempotency key so
    duplicate scheduler calls for the same logical step become
    harmless no-ops.
    """

    idempotency_key = (
        f"live-tick:{observation_ts.isoformat()}"
    )

    cur.execute("""
        INSERT INTO live_ticks (
            observation_ts,
            trigger_type,
            idempotency_key,
            status,
            station_count,
            completed_at,
            error_message
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            CASE
                WHEN %s = 'completed'
                THEN NOW()
                ELSE NULL
            END,
            %s
        )
        ON CONFLICT (idempotency_key)
        DO UPDATE SET
            trigger_type = EXCLUDED.trigger_type,
            status = EXCLUDED.status,
            station_count = EXCLUDED.station_count,
            completed_at = EXCLUDED.completed_at,
            error_message = EXCLUDED.error_message
        RETURNING
            id,
            observation_ts,
            trigger_type,
            idempotency_key,
            status,
            station_count,
            started_at,
            completed_at,
            error_message
    """, (
        observation_ts,
        trigger_type,
        idempotency_key,
        status,
        station_count,
        status,
        error_message,
    ))

    return cur.fetchone()


def get_live_tick_count(cur):
    """Return the number of completed live ticks."""

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM live_ticks
        WHERE status = 'completed'
    """)

    row = cur.fetchone()

    return int(row["count"])


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


def get_station_feature_history_batch(
    station_ids,
    limit=96,
):
    """Return bounded raw history for multiple stations in one query."""

    station_ids = [str(station_id) for station_id in station_ids]

    if not station_ids:
        return []

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    station_id,
                    timestamp,
                    temperature_c,
                    relative_humidity_pct,
                    pressure_hpa
                FROM (
                    SELECT
                        station_id,
                        timestamp,
                        temperature_c,
                        relative_humidity_pct,
                        pressure_hpa,
                        ROW_NUMBER() OVER (
                            PARTITION BY station_id
                            ORDER BY timestamp DESC, id DESC
                        ) AS row_number
                    FROM readings
                    WHERE station_id = ANY(%s)
                      AND source IN (
                          'historical',
                          'live'
                      )
                ) history
                WHERE row_number <= %s
                ORDER BY station_id, timestamp ASC
            """, (
                station_ids,
                limit,
            ))

            return cur.fetchall()


def get_live_anomaly_history(station_ids):
    """Return persisted live anomalies for multiple stations."""

    station_ids = [str(station_id) for station_id in station_ids]

    if not station_ids:
        return []

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    station_id,
                    timestamp,
                    anomaly_score,
                    weather_or_sensor,
                    confidence,
                    fault_component
                FROM readings
                WHERE station_id = ANY(%s)
                  AND source = 'live'
                  AND anomaly = 1
                ORDER BY station_id, timestamp ASC, id ASC
            """, (
                station_ids,
            ))

            return cur.fetchall()


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

            cur.execute("""
                DELETE FROM live_ticks
            """)

            cur.execute("""
                DELETE FROM live_state
            """)

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

            cur.execute("""
                DELETE FROM live_ticks
            """)

            cur.execute("""
                DELETE FROM live_state
            """)

        conn.commit()

    print(
        f"Database reset — {deleted} readings removed."
    )
