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
    get_station_feature_history,
    get_latest_station_context,
    reset_database,
)

from feature_engineering import (
    build_features,
    build_model_row,
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

class RawTelemetry(BaseModel):
    """
    Raw AWS telemetry received by the backend.

    The client supplies ONLY the physical sensor readings.
    Feature engineering happens inside the backend.
    """

    station_id: str
    timestamp: str
    temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    pressure_hpa: float | None = None


class RawTelemetryBatch(BaseModel):
    """
    A contemporaneous network snapshot.

    All readings in one batch are evaluated against the same
    timestamp-level spatial context before any of them are
    persisted as LIVE data.
    """

    readings: list[RawTelemetry]


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
    Build the exact 50-feature vector for a Demo Center
    benchmark observation using the same feature engine
    used by real-time /ingest telemetry.

    The benchmark dataset supplies the raw observation.
    Historical context is retrieved from PostgreSQL.
    """

    station_id = str(
        row.get("station_id", "")
    )

    timestamp = pd.to_datetime(
        row.get("timestamp")
    )

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(
            "Asia/Kolkata"
        )
    else:
        timestamp = timestamp.tz_convert(
            "Asia/Kolkata"
        )

    temperature = row.get(
        "temperature_c"
    )

    humidity = row.get(
        "relative_humidity_pct"
    )

    pressure = row.get(
        "pressure_hpa"
    )

    # --------------------------------------------------------
    # Retrieve station history from PostgreSQL.
    #
    # Demo data is deliberately excluded from the history
    # used by the feature engine.
    # --------------------------------------------------------

    history = get_station_feature_history(
        station_id=station_id,
        before_timestamp=timestamp,
        limit=96,
    )

    # --------------------------------------------------------
    # Retrieve spatial context.
    # --------------------------------------------------------

    station_context = get_latest_station_context(
        timestamp=timestamp,
        max_age_seconds=1800,
    )

    all_station_history = pd.DataFrame(
        station_context
    )

    # Include the current benchmark observation in the
    # spatial context so regional features can be computed.
    if not all_station_history.empty:

        current_context = pd.DataFrame(
            [
                {
                    "station_id": station_id,
                    "timestamp": timestamp,
                    "temperature_c": temperature,
                    "relative_humidity_pct": humidity,
                    "pressure_hpa": pressure,
                }
            ]
        )

        all_station_history = pd.concat(
            [
                all_station_history,
                current_context,
            ],
            ignore_index=True,
        )

    else:

        all_station_history = pd.DataFrame(
            [
                {
                    "station_id": station_id,
                    "timestamp": timestamp,
                    "temperature_c": temperature,
                    "relative_humidity_pct": humidity,
                    "pressure_hpa": pressure,
                }
            ]
        )

    # --------------------------------------------------------
    # Run the canonical feature engine.
    # --------------------------------------------------------

    features = build_features(
        station_id=station_id,
        timestamp=timestamp,
        temperature_c=temperature,
        relative_humidity_pct=humidity,
        pressure_hpa=pressure,
        history=pd.DataFrame(history),
        all_station_history=all_station_history,
    )

    return features


# ============================================================
# EXPLAINABILITY EVIDENCE
# ============================================================

def _evidence_from_feature(
    value,
) -> float:
    """
    Convert an explainability feature into a normalized
    evidence score.

    -999 means the feature is unavailable and therefore
    contributes no evidence.
    """

    if value is None:
        return 0.0

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if value == -999:
        return 0.0

    return min(
        abs(value) / 5,
        1.0,
    )


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

    temporal_evidence = _evidence_from_feature(
        features.get(
            "temperature_zscore_6h"
        )
    )

    spatial_evidence = _evidence_from_feature(
        features.get(
            "regional_temp_zscore"
        )
    )

    multivariate_evidence = _evidence_from_feature(
        features.get(
            "physically_implausible_flag"
        )
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

# ============================================================
# RAW TELEMETRY INGESTION
# ============================================================

def _normalize_ingest_timestamp(timestamp: str):
    """
    Normalize an incoming timestamp to timezone-aware
    Asia/Kolkata time.
    """

    current_timestamp = pd.to_datetime(
        timestamp,
        errors="raise",
    )

    if current_timestamp.tzinfo is None:
        current_timestamp = current_timestamp.tz_localize(
            "Asia/Kolkata"
        )

    return current_timestamp


def _process_live_reading(
    reading: RawTelemetry,
    spatial_context: pd.DataFrame | None = None,
):
    """
    Build the canonical 50-feature vector and run the real
    two-stage ML pipeline for one raw telemetry observation.

    If spatial_context is supplied, it must represent the
    complete contemporaneous network snapshot for this reading.
    """

    current_timestamp = _normalize_ingest_timestamp(
        reading.timestamp
    )

    # --------------------------------------------------------
    # Retrieve previous station history.
    # --------------------------------------------------------

    history_rows = get_station_feature_history(
        station_id=reading.station_id,
        before_timestamp=current_timestamp,
        limit=96,
    )

    history = pd.DataFrame(history_rows)

    if history.empty:
        history = pd.DataFrame(
            columns=[
                "station_id",
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        )

    # --------------------------------------------------------
    # Spatial context.
    #
    # For batch ingestion, the caller supplies the complete
    # timestamp snapshot. For single ingestion, use the exact
    # timestamp context currently present in PostgreSQL.
    # --------------------------------------------------------

    if spatial_context is None:

        spatial_rows = get_latest_station_context(
            timestamp=current_timestamp,
            max_age_seconds=1800,
        )

        all_station_history = pd.DataFrame(
            spatial_rows
        )

    else:

        all_station_history = spatial_context.copy()

    if all_station_history.empty:

        all_station_history = pd.DataFrame(
            columns=[
                "station_id",
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        )

    # --------------------------------------------------------
    # Ensure the current observation is present exactly once.
    # --------------------------------------------------------

    current_spatial_row = pd.DataFrame(
        [
            {
                "station_id":
                    reading.station_id,

                "timestamp":
                    current_timestamp,

                "temperature_c":
                    reading.temperature_c,

                "relative_humidity_pct":
                    reading.relative_humidity_pct,

                "pressure_hpa":
                    reading.pressure_hpa,
            }
        ]
    )

    all_station_history = pd.concat(
        [
            all_station_history,
            current_spatial_row,
        ],
        ignore_index=True,
    )

    # --------------------------------------------------------
    # Build exact 50-feature vector.
    # --------------------------------------------------------

    features = build_features(
        station_id=reading.station_id,
        timestamp=current_timestamp,
        temperature_c=reading.temperature_c,
        relative_humidity_pct=(
            reading.relative_humidity_pct
        ),
        pressure_hpa=reading.pressure_hpa,
        history=history,
        all_station_history=all_station_history,
    )

    model_row = build_model_row(features)

    # --------------------------------------------------------
    # Stage 1 — anomaly detection.
    # --------------------------------------------------------

    anomaly_pred = model_anomaly.predict(
        model_row
    )[0]

    anomaly_proba = model_anomaly.predict_proba(
        model_row
    )[0][1]

    is_anomaly = bool(
        int(anomaly_pred) == 1
    )

    # --------------------------------------------------------
    # Stage 2 — weather vs sensor.
    # --------------------------------------------------------

    weather_or_sensor = "none"
    cause_confidence = None

    if is_anomaly:

        cause_pred = model_cause.predict(
            model_row
        )[0]

        cause_proba = model_cause.predict_proba(
            model_row
        )[0]

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
            float(
                features.get(
                    "temperature_zscore_6h",
                    0,
                )
                or 0
            )
        ),

        "humidity": abs(
            float(
                features.get(
                    "humidity_zscore_6h",
                    0,
                )
                or 0
            )
        ),

        "pressure": abs(
            float(
                features.get(
                    "pressure_zscore_6h",
                    0,
                )
                or 0
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

    temporal_evidence = _evidence_from_feature(
        features.get(
            "temperature_zscore_6h"
        )
    )

    spatial_evidence = _evidence_from_feature(
        features.get(
            "regional_temp_zscore"
        )
    )

    multivariate_evidence = _evidence_from_feature(
        features.get(
            "physically_implausible_flag"
        )
    )

    result = {

        "station_id":
            reading.station_id,

        "timestamp":
            current_timestamp.isoformat(),

        "temperature_c":
            reading.temperature_c,

        "relative_humidity_pct":
            reading.relative_humidity_pct,

        "pressure_hpa":
            reading.pressure_hpa,

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

        "features_computed_count":
            len(features),
    }

    return result


def _persist_live_result(result):
    """
    Persist one already-processed result as LIVE data.
    """

    insert_reading(
        result,
        source="live",
    )


# ============================================================
# RAW TELEMETRY INGESTION
# ============================================================

@app.post("/ingest")
def ingest(
    reading: RawTelemetry,
):
    """
    Single raw AWS telemetry ingestion.

    For a single observation, spatial features use only the
    exact timestamp-level context already available in the
    database plus the current observation.

    For a complete network snapshot, use /ingest/batch.
    """

    try:

        result = _process_live_reading(
            reading
        )

        _persist_live_result(result)

        return result

    except Exception as e:

        import traceback

        traceback.print_exc()

        return {
            "error": str(e)
        }


# ============================================================
# NETWORK SNAPSHOT INGESTION
# ============================================================

@app.post("/ingest/batch")
def ingest_batch(
    batch: RawTelemetryBatch,
):
    """
    Process a contemporaneous AWS network snapshot.

    All readings in the batch must belong to the same timestamp.
    The complete snapshot is constructed in memory first.
    Every station is then evaluated against that same snapshot.

    Raw telemetry is persisted only after all predictions have
    been computed, preventing station arrival order from changing
    spatial features for the batch.
    """

    try:

        if not batch.readings:
            return {
                "error": "Batch must contain at least one reading."
            }

        timestamps = [
            _normalize_ingest_timestamp(
                reading.timestamp
            )
            for reading in batch.readings
        ]

        reference_timestamp = timestamps[0]

        if any(
            timestamp != reference_timestamp
            for timestamp in timestamps
        ):
            return {
                "error":
                    "All readings in a batch must have "
                    "the same timestamp."
            }

        station_ids = [
            reading.station_id.strip()
            for reading in batch.readings
        ]

        if len(station_ids) != len(set(station_ids)):
            return {
                "error":
                    "Batch contains duplicate station_id values."
            }

        # ----------------------------------------------------
        # Existing exact-time context from PostgreSQL.
        #
        # Normally this is empty for a new streaming timestamp.
        # It protects against omitting stations that have already
        # been persisted independently.
        # ----------------------------------------------------

        existing_rows = get_latest_station_context(
            timestamp=reference_timestamp,
            max_age_seconds=1800,
        )

        existing_context = pd.DataFrame(
            existing_rows
        )

        # ----------------------------------------------------
        # Current complete batch snapshot.
        #
        # Batch values take precedence over any existing row
        # for the same station/timestamp.
        # ----------------------------------------------------

        batch_context = pd.DataFrame(
            [
                {
                    "station_id":
                        reading.station_id,

                    "timestamp":
                        reference_timestamp,

                    "temperature_c":
                        reading.temperature_c,

                    "relative_humidity_pct":
                        reading.relative_humidity_pct,

                    "pressure_hpa":
                        reading.pressure_hpa,
                }
                for reading in batch.readings
            ]
        )

        if existing_context.empty:

            spatial_context = batch_context.copy()

        else:

            combined = pd.concat(
                [
                    existing_context,
                    batch_context,
                ],
                ignore_index=True,
            )

            spatial_context = (
                combined
                .drop_duplicates(
                    subset=["station_id"],
                    keep="last",
                )
                .reset_index(drop=True)
            )

        # ----------------------------------------------------
        # Run all predictions against the SAME snapshot.
        #
        # Nothing is persisted until every prediction has been
        # computed.
        # ----------------------------------------------------

        results = []

        for reading in batch.readings:

            result = _process_live_reading(
                reading,
                spatial_context=spatial_context,
            )

            results.append(result)

        # ----------------------------------------------------
        # Persist the completed batch.
        # ----------------------------------------------------

        for result in results:
            _persist_live_result(result)

        return {
            "timestamp":
                reference_timestamp.isoformat(),

            "stations_processed":
                len(results),

            "results":
                results,
        }

    except Exception as e:

        import traceback

        traceback.print_exc()

        return {
            "error": str(e)
        }


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