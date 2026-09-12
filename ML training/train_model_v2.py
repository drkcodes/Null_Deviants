import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

print("Loading dataset...")
df = pd.read_csv("SIH26073_AP_AWS_observations.csv.gz")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
print("Loaded! Shape:", df.shape)

# New feature: how many seconds since this station's previous reading?
# Should always be 900 (15 minutes) if timestamps are in correct order.
df["timestamp_gap_seconds"] = df.groupby("station_id")["timestamp"].diff().dt.total_seconds()
df["timestamp_gap_flag"] = (df["timestamp_gap_seconds"] != 900).astype(int)

# How far is the current reading from the same hour yesterday?
# Slower-moving reference point, much harder for a gradual drift to contaminate.
df["temperature_dev_24h"] = df["temperature_c"] - df["temperature_lag_24h"]
df["humidity_dev_24h"] = df["relative_humidity_pct"] - df["humidity_lag_24h"]
df["pressure_dev_24h"] = df["pressure_hpa"] - df["pressure_lag_24h"]

train_df = df[df["timestamp"] < "2025-11-01"]
test_df = df[df["timestamp"] >= "2025-11-01"]
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
y_train = train_df["anomaly_flag"].astype(int)

X_test = test_df[feature_cols].fillna(-999)
y_test = test_df["anomaly_flag"].astype(int)

print("Training the model... this may take a few minutes")
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=15,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)
print("Training complete!")

predictions = model.predict(X_test)

print("\n--- MODEL PERFORMANCE (Random Forest, Supervised) ---")
print(classification_report(y_test, predictions, target_names=["Normal", "Anomaly"]))

importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
print("\n--- TOP 10 MOST IMPORTANT FEATURES ---")
print(importances.head(10))

joblib.dump(model, "anomaly_model_v2.pkl")
print("\nModel saved as anomaly_model_v2.pkl")

# Break down performance by specific anomaly type
test_df = test_df.copy()
test_df["predicted"] = predictions

print("\n--- PERFORMANCE BY ANOMALY TYPE ---")
for atype in test_df["anomaly_type"].unique():
    if atype == "none":
        continue
    subset = test_df[test_df["anomaly_type"] == atype]
    caught = (subset["predicted"] == 1).sum()
    total = len(subset)
    rate = caught / total if total > 0 else 0
    print(f"{atype:30s}  caught {caught:5d} / {total:5d}  ({rate:.1%})")

print("\n--- DRIFT PERFORMANCE BY SEVERITY ---")
drift_rows = test_df[test_df["anomaly_type"] == "drift"]
for sev in ["LOW", "MEDIUM", "HIGH"]:
    subset = drift_rows[drift_rows["severity"] == sev]
    caught = (subset["predicted"] == 1).sum()
    total = len(subset)
    rate = caught / total if total > 0 else 0
    print(f"{sev:10s}  caught {caught:5d} / {total:5d}  ({rate:.1%})")