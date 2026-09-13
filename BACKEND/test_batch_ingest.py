from pathlib import Path

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "http://127.0.0.1:8000/ingest/batch"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

TARGET_TIMESTAMP = pd.Timestamp(
    "2025-12-31 00:00:00"
)


# ============================================================
# LOAD DATASET
# ============================================================

print("=" * 70)
print("SIH26073 — BATCH INGESTION TEST")
print("=" * 70)

print(f"\nDataset: {DATASET_PATH}")
print(f"Target : {TARGET_TIMESTAMP}")

df = pd.read_csv(
    DATASET_PATH
)

df["timestamp"] = pd.to_datetime(
    df["timestamp"]
)

# ------------------------------------------------------------
# Get exactly one network snapshot.
# ------------------------------------------------------------

snapshot = df[
    df["timestamp"] == TARGET_TIMESTAMP
].copy()

snapshot = (
    snapshot
    .sort_values("station_id")
    .reset_index(drop=True)
)

print(
    f"\nStations found: "
    f"{len(snapshot)}"
)

print(
    f"Unique stations: "
    f"{snapshot['station_id'].nunique()}"
)


# ============================================================
# VALIDATION
# ============================================================

if len(snapshot) != 20:

    raise RuntimeError(
        f"Expected 20 stations but found "
        f"{len(snapshot)}."
    )

if snapshot["station_id"].nunique() != 20:

    raise RuntimeError(
        "Duplicate or missing station IDs "
        "detected in snapshot."
    )


# ============================================================
# BUILD RAW TELEMETRY BATCH
# ============================================================

readings = []

for _, row in snapshot.iterrows():

    readings.append({

        "station_id":
            str(row["station_id"]),

        "timestamp":
            TARGET_TIMESTAMP.isoformat(),

        "temperature_c":
            (
                None
                if pd.isna(row["temperature_c"])
                else float(row["temperature_c"])
            ),

        "relative_humidity_pct":
            (
                None
                if pd.isna(
                    row["relative_humidity_pct"]
                )
                else float(
                    row["relative_humidity_pct"]
                )
            ),

        "pressure_hpa":
            (
                None
                if pd.isna(row["pressure_hpa"])
                else float(row["pressure_hpa"])
            ),
    })


payload = {
    "readings": readings
}


# ============================================================
# SEND BATCH
# ============================================================

print("\nSending complete 20-station snapshot...")

response = requests.post(
    API_URL,
    json=payload,
    timeout=30,
)

print(
    f"HTTP status: {response.status_code}"
)

response.raise_for_status()

result = response.json()


# ============================================================
# DISPLAY RESULT
# ============================================================

if "error" in result:

    raise RuntimeError(
        result["error"]
    )

print(
    "\nTimestamp returned:"
    f" {result.get('timestamp')}"
)

print(
    "Stations processed:"
    f" {result.get('stations_processed')}"
)

results = result.get(
    "results",
    []
)

print(
    f"Results received: {len(results)}"
)


# ============================================================
# CHECK EVERY RESULT
# ============================================================

print("\n" + "-" * 70)
print(
    "STATION RESULTS"
)
print("-" * 70)

for item in results:

    print(
        f"{item['station_id']:10s}"
        f" | anomaly={str(item['anomaly']):5s}"
        f" | score={item['anomaly_score']}"
        f" | classification="
        f"{item['weather_or_sensor']}"
        f" | features="
        f"{item['features_computed_count']}"
    )


# ============================================================
# FINAL VALIDATION
# ============================================================

if result.get("stations_processed") != 20:

    raise RuntimeError(
        "Backend did not process all 20 stations."
    )

if len(results) != 20:

    raise RuntimeError(
        "Backend did not return 20 results."
    )

bad_feature_counts = [
    item
    for item in results
    if item.get(
        "features_computed_count"
    ) != 50
]

if bad_feature_counts:

    raise RuntimeError(
        "One or more stations did not receive "
        "exactly 50 features."
    )


print("\n" + "=" * 70)
print(
    "BATCH TEST PASSED"
)
print("=" * 70)

print(
    "\n20/20 stations processed."
)

print(
    "50/50 features computed for every station."
)

print(
    "All stations were evaluated against "
    "one contemporaneous network snapshot."
)