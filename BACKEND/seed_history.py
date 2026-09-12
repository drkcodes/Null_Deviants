"""
Populate the existing SkyGuardAI SQLite database with genuine historical
benchmark telemetry for every AWS station.

Run from the BACKEND directory:
    python seed_history.py

This script does NOT delete existing ML alert/prediction records. It adds
normal historical telemetry from the real 700,800-row benchmark CSV, using
seven complete days immediately before 2025-12-31 23:45:00.
"""
from pathlib import Path
import sqlite3
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
CSV_PATH = BACKEND_DIR.parent / "ML training" / "SIH26073_AP_AWS_observations.csv"
DB_PATH = BACKEND_DIR / "weatherguard.db"

REQUIRED = ["station_id", "timestamp", "temperature_c", "relative_humidity_pct", "pressure_hpa"]


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Benchmark CSV not found: {CSV_PATH}")
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")

    print(f"Loading benchmark telemetry: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, usecols=REQUIRED)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise RuntimeError(f"CSV is missing required columns: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["station_id", "timestamp"])
    for col in ["temperature_c", "relative_humidity_pct", "pressure_hpa"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Use the same final seven-day benchmark window for every station.
    # Dec 31 is intentionally excluded because the demo database already
    # contains selected Dec 31 ML evaluation records.
    end = pd.Timestamp("2025-12-30 23:45:00")
    start = end - pd.Timedelta(days=7) + pd.Timedelta(minutes=15)
    window = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    window = window.sort_values(["station_id", "timestamp"])

    expected_per_station = 7 * 96
    print(f"Selected window: {start} -> {end}")
    print(f"Rows in window: {len(window):,}")

    conn = sqlite3.connect(DB_PATH)
    try:
        # Verify the existing schema before inserting anything.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(readings)").fetchall()}
        required_db = {
            "station_id", "timestamp", "temperature_c", "relative_humidity_pct",
            "pressure_hpa", "anomaly", "anomaly_score", "weather_or_sensor",
            "confidence", "fault_component", "evidence_temporal",
            "evidence_spatial", "evidence_multivariate",
        }
        missing_db = required_db - cols
        if missing_db:
            raise RuntimeError(f"Unexpected readings schema; missing columns: {sorted(missing_db)}")

        inserted = 0
        skipped = 0
        station_counts = {}

        for station_id, group in window.groupby("station_id", sort=True):
            # Prefer exactly 672 observations; if the source has a small gap,
            # use whatever valid observations exist rather than fabricating data.
            group = group.dropna(subset=["temperature_c", "relative_humidity_pct", "pressure_hpa"])
            station_counts[station_id] = len(group)

            for row in group.itertuples(index=False):
                ts = row.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                exists = conn.execute(
                    "SELECT 1 FROM readings WHERE station_id = ? AND timestamp = ? LIMIT 1",
                    (str(station_id), ts),
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                conn.execute(
                    """INSERT INTO readings (
                        station_id, timestamp, temperature_c, relative_humidity_pct,
                        pressure_hpa, anomaly, anomaly_score, weather_or_sensor,
                        confidence, fault_component, evidence_temporal,
                        evidence_spatial, evidence_multivariate
                    ) VALUES (?, ?, ?, ?, ?, 0, 0.0, 'none', NULL, 'none', 0.0, 0.0, 0.0)""",
                    (
                        str(station_id),
                        ts,
                        float(row.temperature_c),
                        float(row.relative_humidity_pct),
                        float(row.pressure_hpa),
                    ),
                )
                inserted += 1

        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        station_total = conn.execute("SELECT COUNT(DISTINCT station_id) FROM readings").fetchone()[0]
        alerts = conn.execute("SELECT COUNT(*) FROM readings WHERE anomaly = 1").fetchone()[0]

        print(f"Historical rows inserted : {inserted:,}")
        print(f"Existing rows skipped     : {skipped:,}")
        print(f"Database readings total   : {total:,}")
        print(f"Stations represented      : {station_total}")
        print(f"Existing anomaly records  : {alerts}")
        print("\nPer-station historical rows:")
        for station_id, count in sorted(station_counts.items()):
            status = "OK" if count >= expected_per_station else "PARTIAL"
            print(f"  {station_id}: {count:4d}  {status}")

        if station_total < 20:
            raise RuntimeError("Fewer than 20 stations are represented after seeding.")
        print("\nSUCCESS: real benchmark history is now available for the station graphs.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
