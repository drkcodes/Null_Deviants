import pandas as pd
import requests

df = pd.read_csv("SIH26073_AP_AWS_observations.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

df["timestamp_gap_seconds"] = df.groupby("station_id")["timestamp"].diff().dt.total_seconds()
df["timestamp_gap_flag"] = (df["timestamp_gap_seconds"] != 900).astype(int)
df["temperature_dev_24h"] = df["temperature_c"] - df["temperature_lag_24h"]
df["humidity_dev_24h"] = df["relative_humidity_pct"] - df["humidity_lag_24h"]
df["pressure_dev_24h"] = df["pressure_hpa"] - df["pressure_lag_24h"]

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

normal_row = df[df["anomaly_flag"] == False].iloc[5000]
anomaly_row = df[(df["anomaly_flag"] == True) & (df["anomaly_type"] == "spike")].iloc[0]

def send_row(row, label):
    payload = {
        "station_id": row["station_id"],
        "timestamp": str(row["timestamp"]),
        "features": {col: (None if pd.isna(row[col]) else float(row[col])) for col in feature_cols}
    }
    response = requests.post("http://127.0.0.1:8000/predict", json=payload)
    print(f"\n--- {label} ---")
    print("Actual anomaly_type in data:", row["anomaly_type"])
    print("API response:", response.json())

send_row(normal_row, "Testing a NORMAL reading")
send_row(anomaly_row, "Testing a SPIKE anomaly reading")

