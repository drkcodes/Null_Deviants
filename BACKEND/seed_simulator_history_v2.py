"""
D4.2 v2 — Batched, resumable PostgreSQL seeder for the simulator history.

Safety:
- Uses DATABASE_URL from the environment.
- Default mode is DRY-RUN.
- --apply performs additive INSERTs only.
- Inserts source='historical'.
- Never DELETEs, UPDATEs, TRUNCATEs, or RESETs.
- Commits small batches so a hosted DB connection does not have to hold
  thousands of INSERT statements in one transaction.
- Safe to rerun: existing historical/live station+timestamp keys are skipped.
- If a connection dies, already committed batches remain valid and the next
  run resumes from the remaining keys.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from time import sleep

import pandas as pd
import psycopg
from psycopg.rows import dict_row


BACKEND_DIR = Path(__file__).resolve().parent
SEED_PATH = BACKEND_DIR / "simulator_history_seed.csv"

REQUIRED_COLUMNS = [
    "station_id",
    "timestamp",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
]

EXPECTED_STATIONS = 20
BATCH_SIZE = 250
MAX_RETRIES = 3


def load_seed() -> pd.DataFrame:
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Missing seed file: {SEED_PATH}")

    df = pd.read_csv(SEED_PATH)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(f"Seed CSV missing columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()

    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    for col in [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=REQUIRED_COLUMNS)

    df = df.drop_duplicates(
        subset=["station_id", "timestamp"],
        keep="first",
    ).reset_index(drop=True)

    return df


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set the Render PostgreSQL "
            "connection string in this PowerShell session."
        )
    return url


def connect(database_url: str):
    return psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=15,
    )


def validate_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'readings'
            """
        )
        columns = {r["column_name"] for r in cur.fetchall()}

    required = {
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

    missing = required - columns
    if missing:
        raise RuntimeError(
            f"Unexpected readings schema; missing columns: {sorted(missing)}"
        )


def get_counts(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM readings")
        total = cur.fetchone()["n"]

        cur.execute(
            "SELECT COUNT(*) AS n FROM readings WHERE source = 'historical'"
        )
        historical = cur.fetchone()["n"]

        cur.execute(
            """
            SELECT COUNT(DISTINCT station_id) AS n
            FROM readings
            WHERE source = 'historical'
            """
        )
        historical_stations = cur.fetchone()["n"]

    return total, historical, historical_stations


def get_existing_keys(conn, df: pd.DataFrame) -> set[tuple[str, pd.Timestamp]]:
    if df.empty:
        return set()

    timestamps = pd.to_datetime(df["timestamp"], errors="coerce")

    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize("Asia/Kolkata")
    else:
        timestamps = timestamps.dt.tz_convert("Asia/Kolkata")

    min_ts = timestamps.min().tz_convert("UTC").to_pydatetime()
    max_ts = timestamps.max().tz_convert("UTC").to_pydatetime()

    station_ids = sorted(df["station_id"].astype(str).unique())

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT station_id, timestamp
            FROM readings
            WHERE station_id = ANY(%s)
              AND timestamp >= %s
              AND timestamp <= %s
              AND source IN ('historical', 'live')
            """,
            (station_ids, min_ts, max_ts),
        )
        rows = cur.fetchall()

    result = set()

    for row in rows:
        ts = pd.Timestamp(row["timestamp"])

        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")

        result.add((str(row["station_id"]), ts))

    return result


def row_to_params(row):
    timestamp = pd.Timestamp(row.timestamp)

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("Asia/Kolkata")
    else:
        timestamp = timestamp.tz_convert("Asia/Kolkata")

    return (
        str(row.station_id),
        timestamp.to_pydatetime(),
        float(row.temperature_c),
        float(row.relative_humidity_pct),
        float(row.pressure_hpa),
    )


INSERT_SQL = """
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
"""


def insert_batch(database_url: str, batch) -> int:
    """
    Insert one small transaction.

    Retries a whole batch on connection failure. Since the transaction is
    atomic, a failed batch is rolled back by PostgreSQL/connection loss.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with connect(database_url) as conn:
                validate_schema(conn)

                with conn.cursor() as cur:
                    cur.executemany(
                        INSERT_SQL,
                        [row_to_params(row) for row in batch],
                    )

                conn.commit()

            return len(batch)

        except Exception as exc:
            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    f"Batch failed after {MAX_RETRIES} attempts: {exc}"
                ) from exc

            print(
                f"  Batch connection failure "
                f"(attempt {attempt}/{MAX_RETRIES}); retrying..."
            )
            sleep(2 * attempt)

    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually insert historical rows.",
    )
    args = parser.parse_args()

    print("=" * 110)
    print("D4.2 v2 — BATCHED PRODUCTION SIMULATOR HISTORY SEEDER")
    print("=" * 110)
    print(f"Seed file : {SEED_PATH}")
    print(f"Batch size: {BATCH_SIZE}")
    print(
        "MODE      : "
        + (
            "APPLY — PostgreSQL WILL be modified"
            if args.apply
            else "DRY-RUN — PostgreSQL will NOT be modified"
        )
    )
    print()

    df = load_seed()

    print(f"Seed rows : {len(df):,}")
    print(f"Stations  : {df['station_id'].nunique()}")
    print(
        f"Time range: {df['timestamp'].min()} -> "
        f"{df['timestamp'].max()}"
    )
    print()

    if df["station_id"].nunique() != EXPECTED_STATIONS:
        raise RuntimeError(
            f"Expected {EXPECTED_STATIONS} stations, "
            f"found {df['station_id'].nunique()}"
        )

    database_url = get_database_url()

    # Read-only inspection.
    with connect(database_url) as conn:
        validate_schema(conn)

        before_total, before_historical, before_stations = get_counts(conn)
        existing = get_existing_keys(conn, df)

    pending = []

    for row in df.itertuples(index=False):
        ts = pd.Timestamp(row.timestamp)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)

        key = (str(row.station_id), ts)

        if key not in existing:
            pending.append(row)

    print(f"Historical rows before : {before_historical:,}")
    print(f"Historical stations before: {before_stations}")
    print(f"Existing historical/live keys skipped: {len(df) - len(pending):,}")
    print(f"Rows eligible for insertion: {len(pending):,}")
    print()

    if not args.apply:
        print("DRY-RUN COMPLETE")
        print("No INSERT/UPDATE/DELETE/TRUNCATE/RESET executed.")
        print()
        print("If the counts are expected, run:")
        print("  python seed_simulator_history_v2.py --apply")
        print("=" * 110)
        return

    if not pending:
        print("Nothing to insert. Required keys already exist.")
        return

    print("Starting batched insertion...")
    print()

    inserted = 0

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        batch_number = start // BATCH_SIZE + 1
        total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE

        n = insert_batch(database_url, batch)
        inserted += n

        print(
            f"  Batch {batch_number:02d}/{total_batches:02d} "
            f"committed: {n:3d} rows | "
            f"progress: {inserted:,}/{len(pending):,}"
        )

    # Final independent verification.
    with connect(database_url) as conn:
        validate_schema(conn)

        after_total, after_historical, after_stations = get_counts(conn)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT station_id, COUNT(*) AS n
                FROM readings
                WHERE source = 'historical'
                GROUP BY station_id
                ORDER BY station_id
                """
            )
            station_counts = cur.fetchall()

    print()
    print("=" * 110)
    print("D4.2 v2 SEED RESULT")
    print("=" * 110)
    print(f"Historical before : {before_historical:,}")
    print(f"Inserted this run : {inserted:,}")
    print(f"Historical after  : {after_historical:,}")
    print(f"Total before      : {before_total:,}")
    print(f"Total after       : {after_total:,}")
    print(f"Historical stations: {after_stations}")
    print()

    print("PER-STATION HISTORICAL COUNTS")
    print("-" * 110)

    for row in station_counts:
        print(f"  {row['station_id']}: {row['n']:5d}")

    if after_historical < before_historical + inserted:
        raise RuntimeError(
            "Verification failed: historical count is lower than expected."
        )

    if after_stations < EXPECTED_STATIONS:
        raise RuntimeError(
            f"Verification failed: only {after_stations} historical stations."
        )

    print()
    print("SUCCESS")
    print("D4.2 simulator history has been seeded.")
    print("Only source='historical' INSERTs were performed.")
    print("No existing live/demo records were deleted or updated.")
    print("=" * 110)


if __name__ == "__main__":
    main()
