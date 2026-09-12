import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

print("Loading dataset...")
df = pd.read_csv("SIH26073_AP_AWS_observations.csv.gz")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

df["timestamp_gap_seconds"] = df.groupby("station_id")["timestamp"].diff().dt.total_seconds()
df["timestamp_gap_flag"] = (df["timestamp_gap_seconds"] != 900).astype(int)
df["temperature_dev_24h"] = df["temperature_c"] - df["temperature_lag_24h"]
df["humidity_dev_24h"] = df["relative_humidity_pct"] - df["humidity_lag_24h"]
df["pressure_dev_24h"] = df["pressure_hpa"] - df["pressure_lag_24h"]

anomaly_df = df[df["anomaly_flag"] == True].copy()
print("Total anomaly rows to classify:", len(anomaly_df))
print(anomaly_df["weather_or_sensor"].value_counts())

train_df = anomaly_df[anomaly_df["timestamp"] < "2025-11-01"]
test_df = anomaly_df[anomaly_df["timestamp"] >= "2025-11-01"]
print("Training rows:", len(train_df))
print("Testing rows:", len(test_df))

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

X_train = train_df[feature_cols].fillna(-999)
y_train = train_df["weather_or_sensor"]

X_test = test_df[feature_cols].fillna(-999)
y_test = test_df["weather_or_sensor"]

print("Training Stage 2 model...")
model_stage2 = RandomForestClassifier(
    n_estimators=200,
    max_depth=15,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1
)
model_stage2.fit(X_train, y_train)
print("Training complete!")

predictions = model_stage2.predict(X_test)
print("\n--- STAGE 2 PERFORMANCE (Weather vs Sensor Fault) ---")
print(classification_report(y_test, predictions))

importances = pd.Series(model_stage2.feature_importances_, index=feature_cols).sort_values(ascending=False)
print("\n--- TOP 10 FEATURES FOR WEATHER-VS-SENSOR DECISION ---")
print(importances.head(10))

joblib.dump(model_stage2, "model_weather_or_sensor.pkl")
print("\nModel saved as model_weather_or_sensor.pkl")