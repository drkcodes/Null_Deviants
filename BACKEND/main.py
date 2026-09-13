from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import joblib
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

from database import (
    init_db,
    insert_reading,
    get_latest_per_station,
    get_recent_alerts,
    get_station_history,
    reset_database,
)

# ============================================================
# INITIALIZATION
# ============================================================

init_db()

app = FastAPI(
    title="SIH26073 Weather Station Anomaly Detection API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# LOAD ML MODELS
# ============================================================

print("Loading models...")

model_anomaly = joblib.load("model_anomaly_detector.pkl")
model_cause = joblib.load("model_weather_or_sensor.pkl")

print("Models loaded successfully!")

# ============================================================
# MODEL FEATURE VECTOR
# ============================================================

feature_cols = [
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
# DATASET LOCATIONS
# ============================================================

DATASET_CANDIDATES = [
    Path("../ML training/SIH26073_AP_AWS_observations.csv"),
    Path("../Data/claude_DataSet/SIH26073_AP_AWS_observations.csv"),
    Path("SIH26073_AP_AWS_observations.csv"),
]

# ============================================================
# DEMO SCENARIO MAPPING
#
# Supports BOTH the old IDs and the IDs currently used by
# the frontend.
# ============================================================

SIMULATION_TYPE_MAP = {

    # Temperature sensor fault
    "scen-temp-spike": "spike",

    # Temperature sensor fault
    "scen-temp-drop": "drop",

    # Pressure sensor fault
    "scen-pressure-jump": "jump",
    "scen-press-jump": "jump",

    # Genuine regional weather event
    "scen-regional-heatwave": "heatwave",
    "scen-heatwave": "heatwave",

    # Genuine regional weather event
    "scen-regional-cold-spell": "cold_spell",
    "scen-cold-spell": "cold_spell",
}

# Cache benchmark examples after first load.
_simulation_examples = {}


# ============================================================
# REQUEST MODELS
# ============================================================

class SensorReading(BaseModel):
    station_id: str
    timestamp: str
    features: dict


class SimulationRequest(BaseModel):
    station_id: str
    scenario_id: str
    intensity: int = 85


# ============================================================
# DATASET HELPERS
# ============================================================

def _find_dataset() -> Path:
    """
    Find the real SIH26073 benchmark dataset.
    """

    for candidate in DATASET_CANDIDATES:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Training dataset not found. Expected "
        "../ML training/SIH26073_AP_AWS_observations.csv"
    )


def _normalise_timestamp(row: pd.Series) -> str:
    """
    Get a usable timestamp from a benchmark observation.
    """

    value = row.get("timestamp")

    if pd.notna(value):
        return str(value)

    value = row.get("timestamp_utc")

    if pd.notna(value):
        return str(value)

    return pd.Timestamp.utcnow().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _normalise_anomaly_type(value) -> str:
    """
    Normalize different spellings used in the dataset.

    Examples:
        pressure jump
        pressure_jump
        Pressure-Jump
        jump

    all become:
        jump
    """

    if value is None:
        return ""

    value = str(value).strip().lower()

    value = value.replace("-", "_")
    value = value.replace(" ", "_")

    aliases = {
        "temperature_spike": "spike",
        "temp_spike": "spike",

        "temperature_drop": "drop",
        "temp_drop": "drop",

        "pressure_jump": "jump",
        "pressure_jumps": "jump",

        "regional_heatwave": "heatwave",
        "regional_heat_wave": "heatwave",
        "heat_wave": "heatwave",

        "regional_cold_spell": "cold_spell",
        "coldspell": "cold_spell",
        "cold_wave": "cold_spell",
    }

    return aliases.get(value, value)


# ============================================================
# LOAD REAL BENCHMARK EXAMPLES
# ============================================================

def _load_simulation_examples() -> dict:
    """
    Read the benchmark CSV once and cache real observations
    for each station/scenario combination.

    We do NOT fabricate a complete feature vector.

    The observation already contains the model-engineered
    features used during training.
    """

    global _simulation_examples

    if _simulation_examples:
        return _simulation_examples

    dataset_path = _find_dataset()

    print(
        f"Loading benchmark examples from: {dataset_path}"
    )

    # --------------------------------------------------------
    # Read only the header first.
    # --------------------------------------------------------

    header = pd.read_csv(
        dataset_path,
        nrows=0
    )

    available = set(header.columns)

    # --------------------------------------------------------
    # Columns needed by the model + benchmark metadata.
    # --------------------------------------------------------

    required_columns = list(
        dict.fromkeys(
            feature_cols
            + [
                "station_id",
                "timestamp",
                "timestamp_utc",
                "anomaly_type",
                "temperature_lag_24h",
                "humidity_lag_24h",
                "pressure_lag_24h",
            ]
        )
    )

    usecols = [
        column
        for column in required_columns
        if column in available
    ]

    wanted_types = {
        "spike",
        "drop",
        "jump",
        "heatwave",
        "cold_spell",
    }

    found = {}

    # --------------------------------------------------------
    # Read in chunks because the dataset is large.
    # --------------------------------------------------------

    for chunk in pd.read_csv(
        dataset_path,
        usecols=usecols,
        chunksize=100000,
    ):

        if (
            "anomaly_type" not in chunk.columns
            or "station_id" not in chunk.columns
        ):
            continue

        chunk["anomaly_type_norm"] = (
            chunk["anomaly_type"]
            .apply(_normalise_anomaly_type)
        )

        matches = chunk[
            chunk["anomaly_type_norm"].isin(wanted_types)
        ]

        if matches.empty:
            continue

        # ----------------------------------------------------
        # Cache first real benchmark row for each
        # station + anomaly type.
        # ----------------------------------------------------

        for _, row in matches.iterrows():

            station = str(
                row["station_id"]
            ).strip()

            anomaly_type = str(
                row["anomaly_type_norm"]
            )

            key = (
                station,
                anomaly_type,
            )

            if key not in found:
                found[key] = row.to_dict()

        # We have enough when every station has an example
        # for every supported scenario.
        if len(found) >= 20 * len(wanted_types):
            break

    _simulation_examples = found

    print(
        f"Cached benchmark simulation examples: "
        f"{len(found)}"
    )

    return _simulation_examples


# ============================================================
# SELECT BENCHMARK OBSERVATION
# ============================================================

def _select_simulation_row(
    station_id: str,
    scenario_id: str,
) -> dict:

    examples = _load_simulation_examples()

    requested_type = SIMULATION_TYPE_MAP.get(
        scenario_id
    )

    if not requested_type:

        supported = ", ".join(
            sorted(
                SIMULATION_TYPE_MAP.keys()
            )
        )

        raise ValueError(
            f"Unsupported simulation scenario "
            f"'{scenario_id}'. Supported scenario IDs: "
            f"{supported}"
        )

    station_id = station_id.strip()

    # --------------------------------------------------------
    # First preference:
    # exact station + exact scenario.
    # --------------------------------------------------------

    exact_key = (
        station_id,
        requested_type,
    )

    row = examples.get(exact_key)

    if row:
        return row

    # --------------------------------------------------------
    # Fallback:
    # another real station with the same benchmark event.
    #
    # This is preferable to fabricating a reading.
    # --------------------------------------------------------

    for (
        source_station,
        anomaly_type,
    ), candidate in examples.items():

        if anomaly_type == requested_type:

            print(
                f"No {requested_type} benchmark row "
                f"for {station_id}; using real row "
                f"from {source_station}."
            )

            return candidate

    raise ValueError(
        f"No real benchmark observation found "
        f"for anomaly type '{requested_type}'."
    )


# ============================================================
# NUMERIC HELPER
# ============================================================

def _numeric(
    value,
    default=0.0,
) -> float:

    try:

        if value is None or pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


# ============================================================
# BUILD MODEL FEATURES
# ============================================================

def _build_model_features(
    row: dict,
) -> dict:

    """
    Build the exact 50-feature vector expected by
    the serialized Random Forest models.

    Features already present in the benchmark dataset
    are used directly.

    Inference-only fields are calculated here.
    """

    temperature = _numeric(
        row.get("temperature_c")
    )

    humidity = _numeric(
        row.get("relative_humidity_pct")
    )

    pressure = _numeric(
        row.get("pressure_hpa")
    )

    # --------------------------------------------------------
    # 24-hour reference values.
    # --------------------------------------------------------

    temp_lag_24h = _numeric(
        row.get("temperature_lag_24h"),
        temperature,
    )

    hum_lag_24h = _numeric(
        row.get("humidity_lag_24h"),
        humidity,
    )

    press_lag_24h = _numeric(
        row.get("pressure_lag_24h"),
        pressure,
    )

    features = {}

    # --------------------------------------------------------
    # Use benchmark values wherever available.
    # --------------------------------------------------------

    for col in feature_cols:

        if col in row:

            features[col] = _numeric(
                row[col]
            )

        else:

            features[col] = 0.0

    # --------------------------------------------------------
    # Raw telemetry.
    # --------------------------------------------------------

    features["temperature_c"] = temperature

    features["relative_humidity_pct"] = humidity

    features["pressure_hpa"] = pressure

    # --------------------------------------------------------
    # Inference-only temporal features.
    # --------------------------------------------------------

    features[
        "timestamp_gap_seconds"
    ] = 0.0

    features[
        "timestamp_gap_flag"
    ] = 0.0

    features[
        "temperature_dev_24h"
    ] = (
        temperature
        - temp_lag_24h
    )

    features[
        "humidity_dev_24h"
    ] = (
        humidity
        - hum_lag_24h
    )

    features[
        "pressure_dev_24h"
    ] = (
        pressure
        - press_lag_24h
    )

    return features


# ============================================================
# RUN REAL RANDOM FOREST MODELS
# ============================================================

def _run_real_models(
    features: dict,
) -> dict:

    row = (
        pd.DataFrame([features])
        .reindex(columns=feature_cols)
        .fillna(0)
    )

    # --------------------------------------------------------
    # STAGE 1
    # Anomaly Detection
    # --------------------------------------------------------

    anomaly_pred = (
        model_anomaly
        .predict(row)[0]
    )

    anomaly_proba = (
        model_anomaly
        .predict_proba(row)[0][1]
    )

    is_anomaly = bool(
        int(anomaly_pred) == 1
    )

    # --------------------------------------------------------
    # STAGE 2
    # Weather vs Sensor
    # --------------------------------------------------------

    weather_or_sensor = "none"

    cause_confidence = None

    if is_anomaly:

        cause_pred = (
            model_cause
            .predict(row)[0]
        )

        cause_proba = (
            model_cause
            .predict_proba(row)[0]
        )

        weather_or_sensor = str(
            cause_pred
        )

        cause_confidence = float(
            max(cause_proba)
        )

    # --------------------------------------------------------
    # Root-cause component.
    # --------------------------------------------------------

    z_scores = {

        "temperature": abs(
            _numeric(
                features.get(
                    "temperature_zscore_6h"
                )
            )
        ),

        "humidity": abs(
            _numeric(
                features.get(
                    "humidity_zscore_6h"
                )
            )
        ),

        "pressure": abs(
            _numeric(
                features.get(
                    "pressure_zscore_6h"
                )
            )
        ),
    }

    fault_component = "none"

    if (
        is_anomaly
        and weather_or_sensor.lower()
        == "sensor"
    ):

        fault_component = max(
            z_scores,
            key=z_scores.get,
        )

    # --------------------------------------------------------
    # Explainability evidence.
    # --------------------------------------------------------

    temporal_evidence = min(
        abs(
            _numeric(
                features.get(
                    "temperature_zscore_6h"
                )
            )
        ) / 5,
        1.0,
    )

    spatial_evidence = min(
        abs(
            _numeric(
                features.get(
                    "regional_temp_zscore"
                )
            )
        ) / 5,
        1.0,
    )

    multivariate_evidence = min(
        abs(
            _numeric(
                features.get(
                    "dew_point_deficit_c"
                )
            )
        ) / 5,
        1.0,
    )

    return {

        "anomaly": is_anomaly,

        "anomaly_score": round(
            float(anomaly_proba),
            3,
        ),

        "weather_or_sensor":
            weather_or_sensor,

        "confidence": (
            round(
                cause_confidence,
                3,
            )
            if cause_confidence is not None
            else None
        ),

        "fault_component":
            fault_component,

        "evidence": {

            "temporal":
                round(
                    temporal_evidence,
                    3,
                ),

            "spatial":
                round(
                    spatial_evidence,
                    3,
                ),

            "multivariate":
                round(
                    multivariate_evidence,
                    3,
                ),
        },
    }


# ============================================================
# LIVE PREDICTION ENDPOINT
# ============================================================

@app.post("/predict")
def predict(
    reading: SensorReading,
):

    try:

        f = reading.features

        row = (
            pd.DataFrame([f])
            .reindex(columns=feature_cols)
            .fillna(-999)
        )

        # ----------------------------------------------------
        # Stage 1
        # ----------------------------------------------------

        anomaly_pred = (
            model_anomaly
            .predict(row)[0]
        )

        anomaly_proba = (
            model_anomaly
            .predict_proba(row)[0][1]
        )

        is_anomaly = bool(
            int(anomaly_pred) == 1
        )

        # ----------------------------------------------------
        # Stage 2
        # ----------------------------------------------------

        weather_or_sensor = "none"

        cause_confidence = None

        if is_anomaly:

            cause_pred = (
                model_cause
                .predict(row)[0]
            )

            cause_proba = (
                model_cause
                .predict_proba(row)[0]
            )

            weather_or_sensor = str(
                cause_pred
            )

            cause_confidence = float(
                max(cause_proba)
            )

        # ----------------------------------------------------
        # Explainability
        # ----------------------------------------------------

        temporal_evidence = min(
            abs(
                float(
                    f.get(
                        "temperature_zscore_6h"
                    ) or 0
                )
            ) / 5,
            1.0,
        )

        spatial_evidence = min(
            abs(
                float(
                    f.get(
                        "regional_temp_zscore"
                    ) or 0
                )
            ) / 5,
            1.0,
        )

        multivariate_evidence = min(
            abs(
                float(
                    f.get(
                        "dew_point_deficit_c"
                    ) or 0
                )
            ) / 5,
            1.0,
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
                        f.get(
                            "temperature_zscore_6h"
                        ) or 0
                    )
                ),

                "humidity": abs(
                    float(
                        f.get(
                            "humidity_zscore_6h"
                        ) or 0
                    )
                ),

                "pressure": abs(
                    float(
                        f.get(
                            "pressure_zscore_6h"
                        ) or 0
                    )
                ),
            }

            fault_component = max(
                z_scores,
                key=z_scores.get,
            )

        result = {

            "station_id":
                str(reading.station_id),

            "timestamp":
                str(reading.timestamp),

            "temperature_c":
                f.get("temperature_c"),

            "relative_humidity_pct":
                f.get(
                    "relative_humidity_pct"
                ),

            "pressure_hpa":
                f.get("pressure_hpa"),

            "anomaly":
                is_anomaly,

            "anomaly_score":
                round(
                    float(anomaly_proba),
                    3,
                ),

            "weather_or_sensor":
                weather_or_sensor,

            "confidence": (
                round(
                    cause_confidence,
                    3,
                )
                if cause_confidence is not None
                else None
            ),

            "fault_component":
                fault_component,

            "evidence": {

                "temporal":
                    round(
                        temporal_evidence,
                        3,
                    ),

                "spatial":
                    round(
                        spatial_evidence,
                        3,
                    ),

                "multivariate":
                    round(
                        multivariate_evidence,
                        3,
                    ),
            },
        }

        # Persist live reading.
        insert_reading(result, source = "live")

        return result

    except Exception as e:

        import traceback

        traceback.print_exc()

        return {
            "error": str(e)
        }


# ============================================================
# DEMO CENTER SIMULATION ENDPOINT
# ============================================================

@app.post("/simulate")
def simulate(
    request: SimulationRequest,
):

    """
    Controlled Demo Center evaluation.

    IMPORTANT:
    This does NOT invent a synthetic ML feature vector.

    It:

        1. Selects a real benchmark observation.
        2. Builds the complete 50-feature vector.
        3. Runs Stage 1 Random Forest.
        4. Runs Stage 2 Random Forest when required.
        5. Generates evidence.
        6. Persists the result.
        7. Returns the complete Demo Center result.
    """

    try:

        # ----------------------------------------------------
        # Validate intensity.
        # ----------------------------------------------------

        intensity = max(
            0,
            min(
                100,
                int(request.intensity),
            ),
        )

        # ----------------------------------------------------
        # Select a REAL benchmark observation.
        # ----------------------------------------------------

        raw_row = _select_simulation_row(
            request.station_id,
            request.scenario_id,
        )

        # ----------------------------------------------------
        # Build model feature vector.
        # ----------------------------------------------------

        features = _build_model_features(
            raw_row
        )

        # ----------------------------------------------------
        # Run actual ML pipeline.
        # ----------------------------------------------------

        prediction = _run_real_models(
            features
        )

        # ----------------------------------------------------
        # Timestamp.
        # ----------------------------------------------------

        timestamp = _normalise_timestamp(
            pd.Series(raw_row)
        )

        source_station = str(
            raw_row.get(
                "station_id",
                request.station_id,
            )
        )

        benchmark_type = _normalise_anomaly_type(
            raw_row.get(
                "anomaly_type",
                "unknown",
            )
        )

        # ----------------------------------------------------
        # Diagnosis text.
        # ----------------------------------------------------

        if (
            prediction[
                "weather_or_sensor"
            ].lower()
            == "weather"
        ):

            diagnosis = (
                "The trained pipeline classified "
                "this benchmark observation as a "
                "genuine weather event based on "
                "learned spatial and temporal evidence."
            )

        elif (
            prediction[
                "weather_or_sensor"
            ].lower()
            == "sensor"
        ):

            diagnosis = (
                "The trained pipeline classified "
                "this benchmark observation as a "
                "sensor/data anomaly based on "
                "the learned multivariate evidence."
            )

        else:

            diagnosis = (
                "The Stage 1 model did not flag "
                "this benchmark observation as anomalous."
            )

        # ----------------------------------------------------
        # Build result.
        # ----------------------------------------------------

        result = {

            "station_id":
                source_station,

            "timestamp":
                timestamp,

            "temperature_c":
                _numeric(
                    raw_row.get(
                        "temperature_c"
                    )
                ),

            "relative_humidity_pct":
                _numeric(
                    raw_row.get(
                        "relative_humidity_pct"
                    )
                ),

            "pressure_hpa":
                _numeric(
                    raw_row.get(
                        "pressure_hpa"
                    )
                ),

            "anomaly":
                prediction["anomaly"],

            "anomaly_score":
                prediction[
                    "anomaly_score"
                ],

            "weather_or_sensor":
                prediction[
                    "weather_or_sensor"
                ],

            "confidence":
                prediction["confidence"],

            "fault_component":
                prediction[
                    "fault_component"
                ],

            "evidence":
                prediction["evidence"],

            "features_computed_count":
                len(feature_cols),

            "source":
                "SIH26073 benchmark dataset",

            "benchmark_anomaly_type":
                benchmark_type,

            "requested_station_id":
                request.station_id,

            "scenario_id":
                request.scenario_id,

            "intensity":
                intensity,

            "seasonal_baseline": {

                "temperature_c":
                    _numeric(
                        raw_row.get(
                            "temperature_lag_24h"
                        ),
                        _numeric(
                            raw_row.get(
                                "temperature_c"
                            )
                        ),
                    ),

                "relative_humidity_pct":
                    _numeric(
                        raw_row.get(
                            "humidity_lag_24h"
                        ),
                        _numeric(
                            raw_row.get(
                                "relative_humidity_pct"
                            )
                        ),
                    ),

                "pressure_hpa":
                    _numeric(
                        raw_row.get(
                            "pressure_lag_24h"
                        ),
                        _numeric(
                            raw_row.get(
                                "pressure_hpa"
                            )
                        ),
                    ),
            },

            "diagnosis":
                diagnosis,
        }

        # ----------------------------------------------------
        # Persist Demo Center result into SQLite.
        #
        # This allows the rest of the dashboard to see
        # the simulation result as a real backend event.
        # ----------------------------------------------------

        database_result = {

            "station_id":
                source_station,

            "timestamp":
                timestamp,

            "temperature_c":
                result["temperature_c"],

            "relative_humidity_pct":
                result[
                    "relative_humidity_pct"
                ],

            "pressure_hpa":
                result["pressure_hpa"],

            "anomaly":
                result["anomaly"],

            "anomaly_score":
                result["anomaly_score"],

            "weather_or_sensor":
                result[
                    "weather_or_sensor"
                ],

            "confidence":
                result["confidence"],

            "fault_component":
                result[
                    "fault_component"
                ],

            "evidence":
                result["evidence"],
        }

        insert_reading(
            database_result,
            source = "demo"
        )

        return result

    except Exception as e:

        import traceback

        traceback.print_exc()

        return {
            "error": str(e)
        }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def health_check():

    return {
        "status": "running",
        "message":
            "SIH26073 Anomaly Detection API is alive",
    }


# ============================================================
# STATION DATA
# ============================================================

@app.get("/stations/latest")
def stations_latest():

    return get_latest_per_station()


@app.get("/alerts")
def alerts(
    limit: int = 50,
):

    return get_recent_alerts(
        limit
    )


@app.get("/station/{station_id}/history")
def station_history(
    station_id: str,
    limit: int = 50,
):

    return get_station_history(
        station_id,
        limit,
    )


# ============================================================
# STATION METADATA
# ============================================================

stations_df = pd.read_csv(
    "stations.csv"
)


@app.get("/stations")
def stations_metadata():

    return stations_df.to_dict(
        orient="records"
    )


# ============================================================
# DATABASE RESET
# ============================================================

@app.post("/reset")
def reset():

    reset_database()

    return {
        "status":
            "database cleared"
    }