import pandas as pd
import requests
import time

API_URL = "https://null-deviants-sih-2026-be.onrender.com/predict"

print("Loading dataset for simulation...")
df = pd.read_csv("SIH26073_AP_AWS_observations.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

df["timestamp_gap_seconds"] = df.groupby("station_id")["timestamp"].diff().dt.total_seconds()
df["timestamp_gap_flag"] = (df["timestamp_gap_seconds"] != 900).astype(int)
df["temperature_dev_24h"] = df["temperature_c"] - df["temperature_lag_24h"]
df["humidity_dev_24h"] = df["relative_humidity_pct"] - df["humidity_lag_24h"]
df["pressure_dev_24h"] = df["pressure_hpa"] - df["pressure_lag_24h"]
print(f"Loaded {len(df)} total readings across {df.station_id.nunique()} stations")
#hereeee
demo_start = pd.Timestamp("2025-01-05 00:00")
demo_end = pd.Timestamp("2025-01-06 00:00")

demo_df = df[
    (df.timestamp >= demo_start) &
    (df.timestamp < demo_end)
].copy()
demo_df = demo_df.sort_values("timestamp").reset_index(drop=True)
print(f"Demo window: {demo_start} to {demo_end}, {len(demo_df)} readings to replay")

feature_cols = [
    "temperature_c", "relative_humidity_pct", "pressure_hpa",
    "temperature_lag_15min", "temperature_lag_1h", "temperature_lag_3h",
    "temperature_roc_15min", "temperature_roc_1h",
    "temperature_rollmean_1h", "temperature_rollstd_1h",
    "temperature_rollmean_6h", "temperature_rollstd_6h", "temperature_zscore_6h",
    "humidity_lag_15min", "humidity_lag_1h", "humidity_lag_3h",
    "humidity_roc_15min", "humidity_roc_1h",
    "humidity_rollmean_1h", "humidity_rollstd_1h",
    "humidity_rollmean_6h", "humidity_rollstd_6h", "humidity_zscore_6h",
    "pressure_lag_15min", "pressure_lag_1h", "pressure_lag_3h",
    "pressure_roc_15min", "pressure_roc_1h",
    "pressure_rollmean_1h", "pressure_rollstd_1h",
    "pressure_rollmean_6h", "pressure_rollstd_6h", "pressure_zscore_6h",
    "temperature_stuck_count", "humidity_stuck_count", "pressure_stuck_count",
    "dew_point_deficit_c", "physically_implausible_flag",
    "spatial_temp_diff", "spatial_humidity_diff", "spatial_pressure_diff",
    "regional_temp_zscore",
    "is_missing_temperature", "is_missing_humidity", "is_missing_pressure",
    "timestamp_gap_seconds", "timestamp_gap_flag",
    "temperature_dev_24h", "humidity_dev_24h", "pressure_dev_24h",
]

print("\nStarting replay... (this will call your running API for each reading)")
print("Make sure uvicorn is running in another terminal, WITHOUT --reload!\n")

error_count = 0
success_count = 0
alert_count = 0

for idx, row in demo_df.iterrows():
    payload = {
        "station_id": row["station_id"],
        "timestamp": str(row["timestamp"]),
        "features": {col: (None if pd.isna(row[col]) else float(row[col])) for col in feature_cols}
    }

    response = None
    try:
        response = requests.post(API_URL, json=payload, timeout=5)
        result = response.json()

        if "error" in result:
            error_count += 1
            if error_count <= 5:  # only print the first few, so it doesn't spam
                print(f"[SERVER ERROR] row {idx}: {result['error']}")
        else:
            success_count += 1
            if result.get("anomaly"):
                alert_count += 1
                print(f"[ALERT] {row['station_id']} @ {row['timestamp']} -> "
                      f"{result['weather_or_sensor']} ({result['fault_component']}), "
                      f"confidence {result['confidence']}")

    except Exception as e:
        error_count += 1
        body_preview = response.text[:200] if response is not None else "no response received (connection failed)"
        if error_count <= 5:
            print(f"[CONNECTION ERROR] row {idx}: {e}")
            print(f"  Raw response was: {body_preview}")

    time.sleep(0.02)

print(f"\nReplay complete! Success: {success_count}, Errors: {error_count}, Alerts triggered: {alert_count}")