import sqlite3
import pandas as pd
import joblib

# ============================================================
# CONFIGURATION
# ============================================================

CSV_PATH = (
    r"C:\Users\dilee\Desktop\Null_Deviants"
    r"\ML training\SIH26073_AP_AWS_observations.csv"
)

DB_PATH = "weatherguard.db"

# ============================================================
# LOAD MODELS
# ============================================================

print("=" * 60)
print("UJJVAL - DEMO DATABASE SEEDER")
print("=" * 60)

print("\nLoading trained models...")

model_anomaly = joblib.load("model_anomaly_detector.pkl")
model_cause = joblib.load("model_weather_or_sensor.pkl")

print("Stage 1 model loaded.")
print("Stage 2 model loaded.")

# Always use the exact features stored in the trained model.
FEATURE_COLS = list(model_anomaly.feature_names_in_)

print(f"Model feature count: {len(FEATURE_COLS)}")

# Verify both models use the same feature set.
cause_features = list(model_cause.feature_names_in_)

if FEATURE_COLS != cause_features:
    raise RuntimeError(
        "Stage 1 and Stage 2 models do not use the same feature columns."
    )

# ============================================================
# LOAD DATASET
# ============================================================

print("\nLoading AWS benchmark dataset...")
print("This may take a little while because the CSV is ~340 MB.")

df = pd.read_csv(CSV_PATH)

print(f"Dataset loaded: {len(df):,} rows")
print(f"Stations: {df['station_id'].nunique()}")
print(f"Columns: {len(df.columns)}")

# ============================================================
# BUILD INFERENCE-TIME FEATURES
# ============================================================

print("\nPreparing inference features...")

df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df.sort_values(
    ["station_id", "timestamp"]
).reset_index(drop=True)

# ------------------------------------------------------------
# Timestamp gap features
# ------------------------------------------------------------

df["timestamp_gap_seconds"] = (
    df.groupby("station_id")["timestamp"]
      .diff()
      .dt.total_seconds()
)

# First observation of each station has no previous timestamp.
# A normal AWS interval is 900 seconds = 15 minutes.
df["timestamp_gap_seconds"] = (
    df["timestamp_gap_seconds"]
    .fillna(900)
)

df["timestamp_gap_flag"] = (
    df["timestamp_gap_seconds"] != 900
).astype(int)

# ------------------------------------------------------------
# 24-hour deviation features
# ------------------------------------------------------------

df["temperature_dev_24h"] = (
    df["temperature_c"]
    - df["temperature_lag_24h"]
)

df["humidity_dev_24h"] = (
    df["relative_humidity_pct"]
    - df["humidity_lag_24h"]
)

df["pressure_dev_24h"] = (
    df["pressure_hpa"]
    - df["pressure_lag_24h"]
)

# ============================================================
# VERIFY ALL MODEL FEATURES EXIST
# ============================================================

missing_features = [
    col for col in FEATURE_COLS
    if col not in df.columns
]

if missing_features:
    print("\nERROR: Missing model features:")
    for col in missing_features:
        print(f"  - {col}")

    raise RuntimeError(
        "Dataset is missing required model features."
    )

print(
    f"All {len(FEATURE_COLS)} model features are available."
)

# ============================================================
# SELECT DEMO OBSERVATIONS
# ============================================================

print("\nSelecting representative demo observations...")

selected = []

# ------------------------------------------------------------
# 1. One NORMAL observation from every station
# ------------------------------------------------------------

for station_id, group in df.groupby("station_id"):

    normal = group[
        group["anomaly_flag"] == False
    ]

    if len(normal) > 0:
        selected.append(
            normal.iloc[-1]
        )

# ------------------------------------------------------------
# 2. Representative anomaly/weather scenarios
# ------------------------------------------------------------

scenario_keywords = [
    "spike",
    "drop",
    "freeze",
    "drift",
    "jump",
    "multivariate",
    "heatwave",
    "cold_spell",
]

for keyword in scenario_keywords:

    matches = df[
        df["anomaly_type"]
        .astype(str)
        .str.lower()
        .str.contains(
            keyword,
            na=False
        )
    ]

    if len(matches) > 0:

        selected.append(
            matches.iloc[len(matches) // 2]
        )

print(
    f"Selected {len(selected)} demo observations."
)

# ============================================================
# DATABASE
# ============================================================

print("\nConnecting to SQLite database...")

conn = sqlite3.connect(DB_PATH)

cur = conn.cursor()

# Make sure the table exists.
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id TEXT,
        timestamp TEXT,
        temperature_c REAL,
        relative_humidity_pct REAL,
        pressure_hpa REAL,
        anomaly INTEGER,
        anomaly_score REAL,
        weather_or_sensor TEXT,
        confidence REAL,
        fault_component TEXT,
        evidence_temporal REAL,
        evidence_spatial REAL,
        evidence_multivariate REAL
    )
    """
)

# Start with a clean demo database.
cur.execute("DELETE FROM readings")

conn.commit()

print("Existing demo readings cleared.")

# ============================================================
# RUN ACTUAL ML INFERENCE
# ============================================================

print("\nRunning actual ML inference...")

successful = 0
failed = 0

for index, row in enumerate(selected, start=1):

    try:

        # ----------------------------------------------------
        # Build exact model input
        # ----------------------------------------------------

        feature_values = {}

        for col in FEATURE_COLS:

            value = row[col]

            if pd.isna(value):
                # Same defensive behaviour as the API.
                feature_values[col] = -999
            else:
                feature_values[col] = float(value)

        X = pd.DataFrame(
            [feature_values],
            columns=FEATURE_COLS
        )

        # ----------------------------------------------------
        # Stage 1 - Anomaly Detection
        # ----------------------------------------------------

        anomaly_prediction = int(
            model_anomaly.predict(X)[0]
        )

        anomaly_probabilities = (
            model_anomaly.predict_proba(X)[0]
        )

        # Find probability corresponding to class 1.
        anomaly_class_index = list(
            model_anomaly.classes_
        ).index(1)

        anomaly_score = float(
            anomaly_probabilities[
                anomaly_class_index
            ]
        )

        is_anomaly = (
            anomaly_prediction == 1
        )

        # ----------------------------------------------------
        # Stage 2 - Weather vs Sensor
        # ----------------------------------------------------

        weather_or_sensor = "none"
        confidence = None

        if is_anomaly:

            cause_prediction = (
                model_cause.predict(X)[0]
            )

            cause_probabilities = (
                model_cause.predict_proba(X)[0]
            )

            weather_or_sensor = str(
                cause_prediction
            )

            confidence = float(
                max(cause_probabilities)
            )

        # ----------------------------------------------------
        # Evidence calculations
        # ----------------------------------------------------

        temperature_zscore = float(
            row.get(
                "temperature_zscore_6h",
                0
            )
            or 0
        )

        regional_temp_zscore = float(
            row.get(
                "regional_temp_zscore",
                0
            )
            or 0
        )

        dew_point_deficit = float(
            row.get(
                "dew_point_deficit_c",
                0
            )
            or 0
        )

        temporal_evidence = min(
            abs(temperature_zscore) / 5,
            1.0
        )

        spatial_evidence = min(
            abs(regional_temp_zscore) / 5,
            1.0
        )

        multivariate_evidence = min(
            abs(dew_point_deficit) / 5,
            1.0
        )

        # ----------------------------------------------------
        # Fault component
        # ----------------------------------------------------

        fault_component = "none"

        if (
            is_anomaly
            and weather_or_sensor == "sensor"
        ):

            z_scores = {
                "temperature": abs(
                    float(
                        row.get(
                            "temperature_zscore_6h",
                            0
                        )
                        or 0
                    )
                ),

                "humidity": abs(
                    float(
                        row.get(
                            "humidity_zscore_6h",
                            0
                        )
                        or 0
                    )
                ),

                "pressure": abs(
                    float(
                        row.get(
                            "pressure_zscore_6h",
                            0
                        )
                        or 0
                    )
                ),
            }

            fault_component = max(
                z_scores,
                key=z_scores.get
            )

        # ----------------------------------------------------
        # Insert result
        # ----------------------------------------------------

        cur.execute(
            """
            INSERT INTO readings (
                station_id,
                timestamp,
                temperature_c,
                relative_humidity_pct,
                pressure_hpa,
                anomaly,
                anomaly_score,
                weather_or_sensor,
                confidence,
                fault_component,
                evidence_temporal,
                evidence_spatial,
                evidence_multivariate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["station_id"]),
                str(row["timestamp"]),

                float(
                    row["temperature_c"]
                ),

                float(
                    row["relative_humidity_pct"]
                ),

                float(
                    row["pressure_hpa"]
                ),

                anomaly_prediction,

                round(
                    anomaly_score,
                    3
                ),

                weather_or_sensor,

                (
                    round(confidence, 3)
                    if confidence is not None
                    else None
                ),

                fault_component,

                round(
                    temporal_evidence,
                    3
                ),

                round(
                    spatial_evidence,
                    3
                ),

                round(
                    multivariate_evidence,
                    3
                ),
            )
        )

        successful += 1

        print(
            f"[{index:02d}/{len(selected):02d}] "
            f"{row['station_id']} | "
            f"{row['anomaly_type']} | "
            f"Stage1="
            f"{'ANOMALY' if is_anomaly else 'NORMAL'} | "
            f"Stage2="
            f"{weather_or_sensor}"
        )

    except Exception as e:

        failed += 1

        print(
            f"[{index:02d}/{len(selected):02d}] "
            f"FAILED: "
            f"{row.get('station_id', 'UNKNOWN')} | "
            f"{e}"
        )

# ============================================================
# COMMIT
# ============================================================

conn.commit()

# ============================================================
# DATABASE VERIFICATION
# ============================================================

total_readings = cur.execute(
    "SELECT COUNT(*) FROM readings"
).fetchone()[0]

total_stations = cur.execute(
    """
    SELECT COUNT(DISTINCT station_id)
    FROM readings
    """
).fetchone()[0]

total_alerts = cur.execute(
    """
    SELECT COUNT(*)
    FROM readings
    WHERE anomaly = 1
    """
).fetchone()[0]

sensor_faults = cur.execute(
    """
    SELECT COUNT(*)
    FROM readings
    WHERE weather_or_sensor = 'sensor'
    """
).fetchone()[0]

weather_events = cur.execute(
    """
    SELECT COUNT(*)
    FROM readings
    WHERE weather_or_sensor = 'weather'
    """
).fetchone()[0]

# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n")
print("=" * 60)
print("UJJVAL DEMO DATABASE READY")
print("=" * 60)

print(
    f"Dataset observations : {len(df):,}"
)

print(
    f"Demo readings inserted: {successful}"
)

print(
    f"Failed readings       : {failed}"
)

print(
    f"Database readings     : {total_readings}"
)

print(
    f"Stations represented  : {total_stations}"
)

print(
    f"Anomaly alerts        : {total_alerts}"
)

print(
    f"Sensor classifications: {sensor_faults}"
)

print(
    f"Weather classifications: {weather_events}"
)

print("=" * 60)

if total_readings == 0:
    print(
        "WARNING: Database is still empty."
    )
else:
    print(
        "SUCCESS: Backend database contains real ML results."
    )

conn.close()