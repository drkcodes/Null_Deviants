"""
Seed genuine historical benchmark telemetry into SkyGuard AI PostgreSQL.

Run from the BACKEND directory:
    python seed_history.py

This script:
- reads the genuine SIH26073 benchmark CSV
- selects 7 complete days of history
- inserts raw telemetry only
- stores rows with source='historical'
- never deletes or modifies live/demo records
- is safe to run repeatedly
"""

from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row


BACKEND_DIR = Path(__file__).resolve().parent

CSV_PATH = (
    BACKEND_DIR.parent
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

REQUIRED = [
    "station_id",
    "timestamp",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
]

# Seven complete days immediately before Dec 31, 2025.
END = pd.Timestamp("2025-12-30 23:45:00")
START = END - pd.Timedelta(days=7) + pd.Timedelta(minutes=15)

EXPECTED_PER_STATION = 7 * 96


def get_connection():
    import os

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "Set it first, for example:\n"
            '$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"'
        )

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
    )


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Benchmark CSV not found: {CSV_PATH}"
        )

    print(f"Loading benchmark telemetry:")
    print(f"  {CSV_PATH}")

    df = pd.read_csv(
        CSV_PATH,
        usecols=REQUIRED,
    )

    missing = [
        column
        for column in REQUIRED
        if column not in df.columns
    ]

    if missing:
        raise RuntimeError(
            f"CSV is missing required columns: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["station_id", "timestamp"]
    )

    for column in [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # Select the seven-day historical context window.
    window = df[
        (df["timestamp"] >= START)
        & (df["timestamp"] <= END)
    ].copy()

    window = window.sort_values(
        ["station_id", "timestamp"]
    )

    print()
    print(f"Selected window:")
    print(f"  {START} -> {END}")
    print(f"Rows selected: {len(window):,}")
    print(f"Stations: {window['station_id'].nunique()}")

    expected_total = 20 * EXPECTED_PER_STATION

    if len(window) != expected_total:
        print()
        print(
            "WARNING: selected row count differs from "
            f"expected {expected_total:,}."
        )

    with get_connection() as conn:

        # Verify that the active PostgreSQL schema exists.
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'readings'
                """
            )

            columns = {
                row["column_name"]
                for row in cur.fetchall()
            }

        required_db = {
            "station_id",
            "timestamp",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
            "anomaly",
            "anomaly_score",
            "weather_or_sensor",
            "confidence",
            "fault_component",
            "evidence_temporal",
            "evidence_spatial",
            "evidence_multivariate",
            "source",
        }

        missing_db = required_db - columns

        if missing_db:
            raise RuntimeError(
                "Unexpected PostgreSQL readings schema. "
                f"Missing columns: {sorted(missing_db)}"
            )

        inserted = 0
        skipped = 0
        station_counts = {}

        with conn.cursor() as cur:

            for station_id, group in window.groupby(
                "station_id",
                sort=True,
            ):

                group = group.dropna(
                    subset=[
                        "temperature_c",
                        "relative_humidity_pct",
                        "pressure_hpa",
                    ]
                )

                station_id = str(station_id)

                station_counts[station_id] = len(group)

                for row in group.itertuples(index=False):

                    timestamp = pd.Timestamp(
                        row.timestamp
                    )

                    # PostgreSQL uses TIMESTAMPTZ.
                    # Benchmark timestamps are interpreted as
                    # Asia/Kolkata local observations.
                    timestamp = timestamp.tz_localize(
                        "Asia/Kolkata"
                    )

                    # Idempotency check.
                    cur.execute(
                        """
                        SELECT 1
                        FROM readings
                        WHERE station_id = %s
                          AND timestamp = %s
                        LIMIT 1
                        """,
                        (
                            station_id,
                            timestamp.to_pydatetime(),
                        ),
                    )

                    if cur.fetchone():
                        skipped += 1
                        continue

                    cur.execute(
                        """
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
                            0,
                            0.0,
                            'none',
                            NULL,
                            'none',
                            0.0,
                            0.0,
                            0.0,
                            'historical'
                        )
                        """,
                        (
                            station_id,
                            timestamp.to_pydatetime(),
                            float(row.temperature_c),
                            float(row.relative_humidity_pct),
                            float(row.pressure_hpa),
                        ),
                    )

                    inserted += 1

        conn.commit()

        with conn.cursor() as cur:

            cur.execute(
                "SELECT COUNT(*) AS count FROM readings"
            )
            total = cur.fetchone()["count"]

            cur.execute(
                """
                SELECT COUNT(DISTINCT station_id) AS count
                FROM readings
                """
            )
            station_total = cur.fetchone()["count"]

            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM readings
                WHERE source = 'historical'
                """
            )
            historical_total = cur.fetchone()["count"]

            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM readings
                WHERE anomaly = 1
                """
            )
            alerts = cur.fetchone()["count"]

    print()
    print("========================================")
    print(" HISTORICAL SEED RESULT")
    print("========================================")
    print(f"Historical rows inserted : {inserted:,}")
    print(f"Existing rows skipped    : {skipped:,}")
    print(f"Historical rows in DB    : {historical_total:,}")
    print(f"Database readings total  : {total:,}")
    print(f"Stations represented     : {station_total}")
    print(f"Anomaly records          : {alerts}")

    print()
    print("Per-station historical rows:")

    for station_id, count in sorted(
        station_counts.items()
    ):
        status = (
            "OK"
            if count >= EXPECTED_PER_STATION
            else "PARTIAL"
        )

        print(
            f"  {station_id}: "
            f"{count:4d}  {status}"
        )

    if station_total < 20:
        raise RuntimeError(
            "Fewer than 20 stations are represented "
            "after historical seeding."
        )

    print()
    print("SUCCESS")
    print(
        "Real benchmark history is now available "
        "to the canonical feature engine."
    )


if __name__ == "__main__":
    main()
