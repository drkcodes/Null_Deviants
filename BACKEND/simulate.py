import time
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# CURRENT LOCAL SYSTEM CONFIGURATION
# ============================================================

API_URL = "http://127.0.0.1:8000/predict"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

# One benchmark observation = one simulated 15-minute observation.
# We send it every 2 seconds so the presentation feels live.
SEND_INTERVAL_SECONDS = 2.0

# Replay one day of benchmark telemetry.
DEMO_START = pd.Timestamp("2025-01-05 00:00:00")
DEMO_END = pd.Timestamp("2025-01-06 00:00:00")


# ============================================================
# EXACT FEATURES EXPECTED BY THE CURRENT BACKEND MODELS
# ============================================================

FEATURE_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",

    "temperature_lag_15min",
    "temperature_lag_1h",
    "temperature_lag_3h",
    "temperature_roc_15min",
    "temperature_roc_1h",
    "temperature_rollmean_1h",
    "temperature_rollstd_1h",
    "temperature_rollmean_6h",
    "temperature_rollstd_6h",
    "temperature_zscore_6h",

    "humidity_lag_15min",
    "humidity_lag_1h",
    "humidity_lag_3h",
    "humidity_roc_15min",
    "humidity_roc_1h",
    "humidity_rollmean_1h",
    "humidity_rollstd_1h",
    "humidity_rollmean_6h",
    "humidity_rollstd_6h",
    "humidity_zscore_6h",

    "pressure_lag_15min",
    "pressure_lag_1h",
    "pressure_lag_3h",
    "pressure_roc_15min",
    "pressure_roc_1h",
    "pressure_rollmean_1h",
    "pressure_rollstd_1h",
    "pressure_rollmean_6h",
    "pressure_rollstd_6h",
    "pressure_zscore_6h",

    "temperature_stuck_count",
    "humidity_stuck_count",
    "pressure_stuck_count",

    "dew_point_deficit_c",
    "physically_implausible_flag",

    "spatial_temp_diff",
    "spatial_humidity_diff",
    "spatial_pressure_diff",
    "regional_temp_zscore",

    "is_missing_temperature",
    "is_missing_humidity",
    "is_missing_pressure",

    "timestamp_gap_seconds",
    "timestamp_gap_flag",

    "temperature_dev_24h",
    "humidity_dev_24h",
    "pressure_dev_24h",
]


# ============================================================
# LOAD DATASET
# ============================================================

print("=" * 70)
print("SkyGuardAI — LIVE TELEMETRY SIMULATOR")
print("=" * 70)

print(f"\nDataset:")
print(f"  {DATASET_PATH}")

if not DATASET_PATH.exists():
    raise FileNotFoundError(
        f"\nDataset not found:\n{DATASET_PATH}\n"
        "Check that the ML training folder and CSV still exist."
    )

print("\nLoading benchmark telemetry...")

df = pd.read_csv(DATASET_PATH)

df["timestamp"] = pd.to_datetime(df["timestamp"])

df = (
    df.sort_values(["timestamp", "station_id"])
      .reset_index(drop=True)
)

print(f"Loaded {len(df):,} observations")
print(f"Stations: {df['station_id'].nunique()}")


# ============================================================
# COMPUTE THE 3 INFERENCE FEATURES NOT STORED IN THE CSV
# ============================================================

print("\nComputing inference-time features...")

df["timestamp_gap_seconds"] = (
    df.groupby("station_id")["timestamp"]
      .diff()
      .dt.total_seconds()
)

df["timestamp_gap_flag"] = (
    df["timestamp_gap_seconds"].fillna(900) != 900
).astype(int)

df["temperature_dev_24h"] = (
    df["temperature_c"] - df["temperature_lag_24h"]
)

df["humidity_dev_24h"] = (
    df["relative_humidity_pct"] - df["humidity_lag_24h"]
)

df["pressure_dev_24h"] = (
    df["pressure_hpa"] - df["pressure_lag_24h"]
)


# ============================================================
# SELECT DEMO WINDOW
# ============================================================

demo_df = df[
    (df["timestamp"] >= DEMO_START)
    & (df["timestamp"] < DEMO_END)
].copy()

demo_df = (
    demo_df.sort_values(["timestamp", "station_id"])
           .reset_index(drop=True)
)

if demo_df.empty:
    raise RuntimeError(
        f"No observations found between {DEMO_START} and {DEMO_END}."
    )

print(
    f"\nReplay window:"
    f"\n  {DEMO_START}"
    f"\n  {DEMO_END}"
)

print(f"Replay observations: {len(demo_df):,}")


# ============================================================
# CHECK BACKEND
# ============================================================

print("\nChecking local backend...")

try:
    health = requests.get(
        "http://127.0.0.1:8000/",
        timeout=5
    )

    health.raise_for_status()

    print("Backend: ONLINE")

except Exception as exc:
    raise RuntimeError(
        "\nCould not connect to the local FastAPI backend.\n"
        "Make sure Terminal 1 is running:\n\n"
        "python -m uvicorn main:app --host 127.0.0.1 --port 8000\n"
    ) from exc


# ============================================================
# LIVE REPLAY
# ============================================================

print("\n" + "=" * 70)
print("LIVE REPLAY STARTED")
print("=" * 70)

print(
    "\nEach benchmark observation is being ingested through:"
    "\n  simulator.py"
    "\n       ↓"
    "\n  POST /predict"
    "\n       ↓"
    "\n  ML inference"
    "\n       ↓"
    "\n  SQLite"
)

print(
    f"\nSending one observation every {SEND_INTERVAL_SECONDS} seconds."
)

print("\nPress CTRL+C to stop.\n")


success_count = 0
error_count = 0
alert_count = 0


try:
    for _, row in demo_df.iterrows():

        # ----------------------------------------------------
        # Use the CURRENT clock for the simulated timestamp.
        #
        # This makes the dashboard behave like a current stream
        # instead of remaining stuck in January 2025.
        # ----------------------------------------------------

        simulated_timestamp = pd.Timestamp.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        features = {}

        for col in FEATURE_COLS:
            value = row[col]

            if pd.isna(value):
                features[col] = None
            else:
                features[col] = float(value)

        payload = {
            "station_id": str(row["station_id"]),
            "timestamp": simulated_timestamp,
            "features": features,
        }

        try:
            response = requests.post(
                API_URL,
                json=payload,
                timeout=5
            )

            response.raise_for_status()

            result = response.json()

            if "error" in result:
                error_count += 1

                print(
                    f"[SERVER ERROR] "
                    f"{row['station_id']} → "
                    f"{result['error']}"
                )

            else:
                success_count += 1

                if result.get("anomaly"):
                    alert_count += 1

                    classification = result.get(
                        "weather_or_sensor",
                        "unknown"
                    )

                    component = result.get(
                        "fault_component",
                        "none"
                    )

                    confidence = result.get(
                        "confidence"
                    )

                    print(
                        f"[🚨 ANOMALY] "
                        f"{row['station_id']} | "
                        f"{classification} | "
                        f"{component} | "
                        f"confidence={confidence}"
                    )

                else:
                    print(
                        f"[OK] "
                        f"{row['station_id']} | "
                        f"T={row['temperature_c']:.2f}°C | "
                        f"RH={row['relative_humidity_pct']:.2f}% | "
                        f"P={row['pressure_hpa']:.2f} hPa"
                    )

        except Exception as exc:
            error_count += 1

            print(
                f"[CONNECTION ERROR] "
                f"{row['station_id']} → {exc}"
            )

        time.sleep(SEND_INTERVAL_SECONDS)


except KeyboardInterrupt:

    print("\n\nStopping simulator...")


finally:

    print("\n" + "=" * 70)
    print("SIMULATOR STOPPED")
    print("=" * 70)

    print(f"Successful ingestions : {success_count}")
    print(f"Errors                : {error_count}")
    print(f"Anomalies detected    : {alert_count}")

    print("\nThe simulator can be started again with:")
    print("  python simulate.py")