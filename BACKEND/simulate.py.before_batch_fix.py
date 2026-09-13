import time
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# LOCAL SYSTEM CONFIGURATION
# ============================================================

API_URL = "http://127.0.0.1:8000/ingest"
HEALTH_URL = "http://127.0.0.1:8000/"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

# One simulated 15-minute weather observation is sent every
# 2 seconds so the dashboard feels live during the demo.
SEND_INTERVAL_SECONDS = 2.0

SIMULATED_STEP = pd.Timedelta(minutes=15)


# ============================================================
# REPLAY WINDOW
# ============================================================

# PostgreSQL historical context:
#
#   2025-12-24 00:00
#          ↓
#   2025-12-30 23:45
#
# The simulator therefore starts immediately afterwards.
#
# Every benchmark timestamp contains observations from the
# AWS stations. All stations at one timestamp receive the
# SAME simulated timestamp before the clock advances.

DEMO_START = pd.Timestamp(
    "2025-12-31 00:00:00"
)

DEMO_END = pd.Timestamp(
    "2026-01-01 00:00:00"
)


# ============================================================
# LOAD DATASET
# ============================================================

print("=" * 70)
print("SkyGuardAI - LIVE TELEMETRY SIMULATOR")
print("=" * 70)

print("\nDataset:")
print(f"  {DATASET_PATH}")

if not DATASET_PATH.exists():

    raise FileNotFoundError(
        f"\nDataset not found:\n{DATASET_PATH}\n"
        "Check that the ML training folder and CSV still exist."
    )

print("\nLoading benchmark telemetry...")

df = pd.read_csv(
    DATASET_PATH
)

df["timestamp"] = pd.to_datetime(
    df["timestamp"]
)

df = (
    df.sort_values(
        [
            "timestamp",
            "station_id",
        ]
    )
    .reset_index(drop=True)
)

print(
    f"Loaded {len(df):,} observations"
)

print(
    f"Stations: {df['station_id'].nunique()}"
)


# ============================================================
# SELECT DEMO WINDOW
# ============================================================

demo_df = df[
    (df["timestamp"] >= DEMO_START)
    & (df["timestamp"] < DEMO_END)
].copy()

demo_df = (
    demo_df.sort_values(
        [
            "timestamp",
            "station_id",
        ]
    )
    .reset_index(drop=True)
)

if demo_df.empty:

    raise RuntimeError(
        f"No observations found between "
        f"{DEMO_START} and {DEMO_END}."
    )

print(
    "\nReplay window:"
    f"\n  {DEMO_START}"
    f"\n  {DEMO_END}"
)

print(
    f"Replay observations: {len(demo_df):,}"
)

print(
    f"Simulated interval: "
    f"{SIMULATED_STEP}"
)


# ============================================================
# VERIFY STATION/TIMESTAMP STRUCTURE
# ============================================================

unique_timestamps = (
    demo_df["timestamp"]
    .drop_duplicates()
    .sort_values()
    .reset_index(drop=True)
)

print(
    f"Unique simulated timestamps: "
    f"{len(unique_timestamps):,}"
)

expected_stations = df["station_id"].nunique()

if expected_stations != 20:

    raise RuntimeError(
        f"Expected 20 AWS stations, "
        f"but found {expected_stations}."
    )

rows_per_timestamp = (
    demo_df
    .groupby("timestamp")["station_id"]
    .nunique()
)

incomplete_timestamps = rows_per_timestamp[
    rows_per_timestamp < expected_stations
]

if not incomplete_timestamps.empty:

    print(
        "\nWARNING:"
        f" {len(incomplete_timestamps)} "
        "benchmark timestamps do not contain "
        "all 20 stations."
    )

    print(
        "The simulator will use the observations "
        "that actually exist in the benchmark."
    )


# ============================================================
# CHECK BACKEND
# ============================================================

print("\nChecking local backend...")

try:

    health = requests.get(
        HEALTH_URL,
        timeout=5,
    )

    health.raise_for_status()

    print("Backend: ONLINE")

except Exception as exc:

    raise RuntimeError(
        "\nCould not connect to the local FastAPI backend.\n"
        "Make sure Terminal 1 is running:\n\n"
        "python -m uvicorn main:app "
        "--host 127.0.0.1 --port 8000\n"
    ) from exc


# ============================================================
# LIVE REPLAY
# ============================================================

print("\n" + "=" * 70)
print("LIVE REPLAY STARTED")
print("=" * 70)

print(
    "\nPipeline:"
    "\n  genuine benchmark raw telemetry"
    "\n       -> simulator.py"
    "\n       -> POST /ingest"
    "\n       -> backend feature engine"
    "\n       -> 50 model features"
    "\n       -> Stage 1 anomaly detection"
    "\n       -> Stage 2 weather vs sensor"
    "\n       -> evidence + confidence"
    "\n       -> PostgreSQL"
)

print(
    f"\nSending one observation every "
    f"{SEND_INTERVAL_SECONDS} seconds."
)

print(
    "\nSimulated clock:"
    "\n  +15 minutes per benchmark observation"
)

print(
    "\nSpatial ordering:"
    "\n  all available stations at the same "
    "\n  simulated timestamp are sent together."
)

print("\nPress CTRL+C to stop.\n")


success_count = 0
error_count = 0
alert_count = 0

simulated_timestamp = (
    DEMO_START
    .tz_localize("Asia/Kolkata")
)


# ============================================================
# GROUP BY BENCHMARK TIMESTAMP
# ============================================================

# This is the critical part.
#
# We DO NOT increment simulated time for every station.
#
# Instead:
#
#   benchmark timestamp
#       ↓
#   all stations
#       ↓
#   simulated clock +15 minutes
#       ↓
#   next benchmark timestamp
#
# This gives the spatial feature engine multiple stations
# at exactly the same timestamp.

timestamp_groups = demo_df.groupby(
    "timestamp",
    sort=True,
)


# ============================================================
# START REPLAY
# ============================================================

try:

    for benchmark_timestamp, group in timestamp_groups:

        current_timestamp = simulated_timestamp

        print(
            "\n"
            + "-" * 70
        )

        print(
            f"SIMULATED TIME: "
            f"{current_timestamp.isoformat()}"
        )

        print(
            f"Benchmark time: "
            f"{benchmark_timestamp}"
        )

        print(
            f"Stations this timestamp: "
            f"{len(group)}"
        )

        # ----------------------------------------------------
        # SEND ALL STATIONS FOR THIS TIMESTAMP
        # ----------------------------------------------------

        for _, row in group.iterrows():

            payload = {

                "station_id":
                    str(
                        row["station_id"]
                    ),

                "timestamp":
                    current_timestamp.isoformat(),

                # ------------------------------------------------
                # RAW TELEMETRY ONLY
                #
                # IMPORTANT:
                # No pre-engineered features are sent.
                #
                # The backend computes all 50 model features.
                # ------------------------------------------------

                "temperature_c":
                    (
                        None
                        if pd.isna(
                            row["temperature_c"]
                        )
                        else float(
                            row["temperature_c"]
                        )
                    ),

                "relative_humidity_pct":
                    (
                        None
                        if pd.isna(
                            row["relative_humidity_pct"]
                        )
                        else float(
                            row[
                                "relative_humidity_pct"
                            ]
                        )
                    ),

                "pressure_hpa":
                    (
                        None
                        if pd.isna(
                            row["pressure_hpa"]
                        )
                        else float(
                            row["pressure_hpa"]
                        )
                    ),
            }

            try:

                response = requests.post(
                    API_URL,
                    json=payload,
                    timeout=5,
                )

                response.raise_for_status()

                result = response.json()

                if "error" in result:

                    error_count += 1

                    print(
                        f"[SERVER ERROR] "
                        f"{row['station_id']} -> "
                        f"{result['error']}"
                    )

                else:

                    success_count += 1

                    if result.get("anomaly"):

                        alert_count += 1

                        classification = result.get(
                            "weather_or_sensor",
                            "unknown",
                        )

                        component = result.get(
                            "fault_component",
                            "none",
                        )

                        confidence = result.get(
                            "confidence"
                        )

                        print(
                            f"[ANOMALY] "
                            f"{current_timestamp.isoformat()} | "
                            f"{row['station_id']} | "
                            f"{classification} | "
                            f"{component} | "
                            f"confidence={confidence}"
                        )

                    else:

                        print(
                            f"[OK] "
                            f"{current_timestamp.isoformat()} | "
                            f"{row['station_id']} | "
                            f"T={payload['temperature_c']:.2f} C | "
                            f"RH={payload['relative_humidity_pct']:.2f}% | "
                            f"P={payload['pressure_hpa']:.2f} hPa"
                        )

            except Exception as exc:

                error_count += 1

                print(
                    f"[CONNECTION ERROR] "
                    f"{row['station_id']} -> "
                    f"{exc}"
                )

            time.sleep(
                SEND_INTERVAL_SECONDS
            )

        # ----------------------------------------------------
        # ADVANCE SIMULATED CLOCK ONLY AFTER ALL STATIONS
        # FOR THIS TIMESTAMP HAVE BEEN PROCESSED.
        # ----------------------------------------------------

        simulated_timestamp += SIMULATED_STEP


except KeyboardInterrupt:

    print(
        "\n\nStopping simulator..."
    )


finally:

    print("\n" + "=" * 70)
    print("SIMULATOR STOPPED")
    print("=" * 70)

    print(
        f"Successful ingestions : "
        f"{success_count}"
    )

    print(
        f"Errors                : "
        f"{error_count}"
    )

    print(
        f"Anomalies detected    : "
        f"{alert_count}"
    )

    print(
        "\nThe simulator can be started again with:"
    )

    print(
        "  python simulate.py"
    )