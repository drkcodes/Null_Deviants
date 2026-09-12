from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import joblib

from fastapi.middleware.cors import CORSMiddleware

from database import init_db, insert_reading, get_latest_per_station, get_recent_alerts, get_station_history, reset_database
init_db()

app = FastAPI(title="SIH26073 Weather Station Anomaly Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading models...")
model_anomaly = joblib.load("model_anomaly_detector.pkl")
model_cause = joblib.load("model_weather_or_sensor.pkl")
print("Models loaded successfully!")

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


class SensorReading(BaseModel):
    station_id: str
    timestamp: str
    features: dict


@app.post("/predict")
def predict(reading: SensorReading):
    try:
        f = reading.features

        # Build the row defensively: reindex against feature_cols instead of
        # direct [] selection, so a missing key fills with NaN instead of
        # crashing with a KeyError.
        row = pd.DataFrame([f]).reindex(columns=feature_cols).fillna(-999)

        # Stage 1: is this reading anomalous?
        anomaly_pred = model_anomaly.predict(row)[0]
        anomaly_proba = model_anomaly.predict_proba(row)[0][1]
        is_anomaly = bool(int(anomaly_pred) == 1)

        weather_or_sensor = "none"
        cause_confidence = None

        if is_anomaly:
            cause_pred = model_cause.predict(row)[0]
            cause_proba = model_cause.predict_proba(row)[0]
            weather_or_sensor = str(cause_pred)  # force plain python str, not numpy.str_
            cause_confidence = float(max(cause_proba))

        temporal_evidence = min(abs(float(f.get("temperature_zscore_6h") or 0)) / 5, 1.0)
        spatial_evidence = min(abs(float(f.get("regional_temp_zscore") or 0)) / 5, 1.0)
        multivariate_evidence = min(abs(float(f.get("dew_point_deficit_c") or 0)) / 5, 1.0)

        fault_component = "none"
        if is_anomaly and weather_or_sensor == "sensor":
            z_scores = {
                "temperature": abs(float(f.get("temperature_zscore_6h") or 0)),
                "humidity": abs(float(f.get("humidity_zscore_6h") or 0)),
                "pressure": abs(float(f.get("pressure_zscore_6h") or 0)),
            }
            fault_component = max(z_scores, key=z_scores.get)

        result = {
            "station_id": str(reading.station_id),
            "timestamp": str(reading.timestamp),
            "temperature_c": f.get("temperature_c"),
            "relative_humidity_pct": f.get("relative_humidity_pct"),
            "pressure_hpa": f.get("pressure_hpa"),
            "anomaly": is_anomaly,
            "anomaly_score": round(float(anomaly_proba), 3),
            "weather_or_sensor": weather_or_sensor,
            "confidence": round(cause_confidence, 3) if cause_confidence is not None else None,
            "fault_component": fault_component,
            "evidence": {
                "temporal": round(temporal_evidence, 3),
                "spatial": round(spatial_evidence, 3),
                "multivariate": round(multivariate_evidence, 3),
            },
        }

        insert_reading(result)
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()  # prints the FULL error to Terminal 1, not just the message
        return {"error": str(e)}


@app.get("/")
def health_check():
    return {"status": "running", "message": "SIH26073 Anomaly Detection API is alive"}


@app.get("/stations/latest")
def stations_latest():
    return get_latest_per_station()


@app.get("/alerts")
def alerts(limit: int = 50):
    return get_recent_alerts(limit)


@app.get("/station/{station_id}/history")
def station_history(station_id: str, limit: int = 50):
    return get_station_history(station_id, limit)

stations_df = pd.read_csv("stations.csv")

@app.get("/stations")
def stations_metadata():
    return stations_df.to_dict(orient="records")

@app.post("/reset")
def reset():
    reset_database()
    return {"status": "database cleared"}