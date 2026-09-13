import sys
import time
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000/ingest/batch"

DATASET_PATH = r"C:\Users\dilee\Desktop\Null_Deviants\ML training\SIH26073_AP_AWS_observations.csv"

START_TIMESTAMP = "2025-12-31 00:00:00"
NUM_TIMESTAMPS = 5

print("=" * 70)
print("SIH26073 — SEQUENTIAL CLEAN BATCH TEST")
print("=" * 70)

print(f"\nDataset : {DATASET_PATH}")
print(f"Start   : {START_TIMESTAMP}")
print(f"Steps   : {NUM_TIMESTAMPS}")

# ------------------------------------------------------------
# Load dataset
# ------------------------------------------------------------

try:
    df = pd.read_csv(DATASET_PATH)
except Exception as e:
    print(f"\nERROR: Could not load dataset:\n{e}")
    sys.exit(1)

df["timestamp"] = pd.to_datetime(df["timestamp"])

start = pd.Timestamp(START_TIMESTAMP)

timestamps = sorted(
    df.loc[df["timestamp"] >= start, "timestamp"].unique()
)[:NUM_TIMESTAMPS]

if len(timestamps) != NUM_TIMESTAMPS:
    print(
        f"\nERROR: Expected {NUM_TIMESTAMPS} timestamps "
        f"but found {len(timestamps)}."
    )
    sys.exit(1)

print("\nTimestamps selected:")
for ts in timestamps:
    print(f"  {ts}")

# ------------------------------------------------------------
# Test each complete network snapshot
# ------------------------------------------------------------

total_results = 0
total_anomalies = 0

for step, ts in enumerate(timestamps, start=1):

    print("\n" + "-" * 70)
    print(f"TIMESTAMP {step}/{NUM_TIMESTAMPS}: {ts}")
    print("-" * 70)

    snapshot = df[df["timestamp"] == ts].copy()

    stations = snapshot["station_id"].nunique()

    print(f"Stations: {stations}")

    if stations != 20:
        print(
            f"ERROR: Expected 20 stations, found {stations}."
        )
        sys.exit(1)

    readings = []

    for _, row in snapshot.iterrows():
        readings.append({
            "station_id": row["station_id"],
            "timestamp": row["timestamp"].isoformat(),
            "temperature_c": float(row["temperature_c"]),
            "relative_humidity_pct": float(row["relative_humidity_pct"]),
            "pressure_hpa": float(row["pressure_hpa"]),
        })

    payload = {
        "readings": readings
    }

    try:
        response = requests.post(
            API_URL,
            json=payload,
            timeout=60
        )
    except Exception as e:
        print(f"\nERROR: Request failed:\n{e}")
        sys.exit(1)

    print(f"HTTP status: {response.status_code}")

    if response.status_code != 200:
        print("\nERROR: Backend rejected batch.")
        print(response.text)
        sys.exit(1)

    data = response.json()

    results = data.get("results", [])

    print(f"Results: {len(results)}")

    if len(results) != 20:
        print(
            f"ERROR: Expected 20 results, got {len(results)}."
        )
        sys.exit(1)

    anomalies = 0

    for result in results:

        station = result.get("station_id")
        anomaly = result.get("anomaly")
        score = result.get("anomaly_score")
        features = result.get("features_computed_count")

        if anomaly:
            anomalies += 1

        total_results += 1

        print(
            f"{station:<10} | "
            f"anomaly={str(anomaly):<5} | "
            f"score={score} | "
            f"features={features}"
        )

        if features != 50:
            print(
                f"\nERROR: {station} did not produce 50 features."
            )
            sys.exit(1)

    total_anomalies += anomalies

    print(f"\nAnomalies this timestamp: {anomalies}")

    # Small delay so this behaves like sequential streaming.
    if step < NUM_TIMESTAMPS:
        time.sleep(1)

# ------------------------------------------------------------
# Final result
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("SEQUENTIAL CLEAN TEST COMPLETE")
print("=" * 70)

print(f"\nTimestamps tested : {NUM_TIMESTAMPS}")
print(f"Total predictions : {total_results}")
print(f"Total anomalies   : {total_anomalies}")

print("\nExpected:")
print("  • 20 stations per timestamp")
print("  • 50 features per station")
print("  • No artificial anomalies injected")

print("\nRESULT:")

if total_results == NUM_TIMESTAMPS * 20 and total_anomalies == 0:
    print("SEQUENTIAL CLEAN TEST PASSED")
    sys.exit(0)

print("SEQUENTIAL CLEAN TEST REQUIRES INVESTIGATION")
sys.exit(1)