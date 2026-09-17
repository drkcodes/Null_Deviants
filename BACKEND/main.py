from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
import joblib
import logging
import shap
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

from database import (
    init_db,
    insert_reading,
    get_latest_per_station,
    get_recent_alerts,
    get_station_history,
    get_station_feature_history,
    get_station_feature_history_batch,
    get_live_anomaly_history,
    get_latest_station_context,
    reset_database,
)

from feature_engineering import (
    build_features,
    build_model_row,
)

from maintenance_risk import (
    risk_from_health,
    attach_trajectory_and_horizon,
    rank_maintenance_results,
)

logger = logging.getLogger(__name__)

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
anomaly_explainer = shap.TreeExplainer(model_anomaly)

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

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

DATASET_CANDIDATES = [
    BACKEND_DIR / "SIH26073_AP_AWS_observations.csv",
    PROJECT_DIR / "ML training" / "SIH26073_AP_AWS_observations.csv",
    PROJECT_DIR / "Data" / "claude_DataSet" / "SIH26073_AP_AWS_observations.csv",
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
    Load the curated SIH26073 benchmark observations used by
    the Demo Center.

    The compact backend fixture contains one real benchmark
    observation for every station + supported scenario
    combination. These observations are selected from the
    full SIH26073 benchmark dataset and are used only as
    controlled simulation inputs.

    The actual model feature engineering, network evidence,
    and Random Forest inference remain unchanged.
    """

    global _simulation_examples

    if _simulation_examples:
        return _simulation_examples

    dataset_path = _find_dataset()

    print(
        f"Loading curated benchmark examples from: "
        f"{dataset_path}"
    )

    required_columns = [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "anomaly_type",
    ]

    header = pd.read_csv(
        dataset_path,
        nrows=0,
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in header.columns
    ]

    if missing_columns:
        raise ValueError(
            "Simulation benchmark fixture is missing "
            f"required columns: {missing_columns}"
        )

    fixture = pd.read_csv(
        dataset_path,
        usecols=required_columns,
    )

    fixture["station_id"] = (
        fixture["station_id"]
        .astype(str)
        .str.strip()
    )

    fixture["anomaly_type_norm"] = (
        fixture["anomaly_type"]
        .apply(_normalise_anomaly_type)
    )

    wanted_types = {
        "spike",
        "drop",
        "jump",
        "heatwave",
        "cold_spell",
    }

    fixture = fixture[
        fixture["anomaly_type_norm"].isin(wanted_types)
    ].copy()

    found = {}

    for _, row in fixture.iterrows():

        station_id = str(
            row["station_id"]
        ).strip()

        anomaly_type = str(
            row["anomaly_type_norm"]
        ).strip()

        key = (
            station_id,
            anomaly_type,
        )

        # The compact fixture is intentionally curated with
        # exactly one target observation per station/scenario.
        if key in found:
            raise ValueError(
                "Duplicate curated simulation observation "
                f"for station={station_id}, "
                f"scenario={anomaly_type}"
            )

        found[key] = {
            "station_id": station_id,
            "timestamp": str(
                row["timestamp"]
            ),
            "temperature_c": float(
                row["temperature_c"]
            ),
            "relative_humidity_pct": float(
                row["relative_humidity_pct"]
            ),
            "pressure_hpa": float(
                row["pressure_hpa"]
            ),
            "anomaly_type": anomaly_type,
        }

    expected_count = 20 * len(wanted_types)

    if len(found) != expected_count:
        raise ValueError(
            "Curated simulation fixture is incomplete. "
            f"Expected {expected_count} station/scenario "
            f"observations, found {len(found)}."
        )

    _simulation_examples = found

    print(
        f"Loaded {len(found)} curated simulation "
        "observations."
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


def _clip01(value):
    return max(0.0, min(1.0, float(value)))


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        value = float(value)
        if not pd.notna(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def _context_dataframe(rows):
    """
    Convert database context rows into a dataframe with stable
    column names. Supports both tuple rows and dict-like rows.
    """
    columns = [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]

    if rows is None:
        return pd.DataFrame(columns=columns)

    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
        if len(frame.columns) == len(columns):
            frame.columns = columns
        return frame

    if not rows:
        return pd.DataFrame(columns=columns)

    first = rows[0]

    if isinstance(first, dict):
        frame = pd.DataFrame(rows)
        for column in columns:
            if column not in frame.columns:
                frame[column] = None
        return frame[columns]

    return pd.DataFrame(rows, columns=columns)


def _feature_evidence(value, scale=5.0):
    """
    Normalize a continuous feature into [0, 1].

    -999 and missing values mean unavailable evidence.
    """
    value = _safe_float(value)

    if value is None or value == -999:
        return 0.0

    if scale <= 0:
        return 0.0

    return _clip01(abs(value) / scale)


def _previous_network_context(timestamp):
    """
    Retrieve the exact preceding 15-minute network snapshot.

    Exact-time matching is deliberate: a spatial comparison must
    never substitute an earlier or later observation.
    """
    previous_timestamp = timestamp - pd.Timedelta(minutes=15)

    rows = get_latest_station_context(
        timestamp=previous_timestamp,
        max_age_seconds=1800,
    )

    return _context_dataframe(rows)


def _calculate_network_evidence(
    station_id,
    timestamp,
    current_context,
    previous_context,
    features,
    station_history=None,
):
    """
    Calculate explicit spatiotemporal evidence.

    Core SIH distinction:
        coherent network movement -> weather
        isolated station movement -> sensor

    Only Temperature, Relative Humidity and Pressure are used.
    """

    value_columns = [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]

    current = _context_dataframe(
        current_context.to_dict("records")
        if isinstance(current_context, pd.DataFrame)
        else current_context
    )

    previous = _context_dataframe(
        previous_context.to_dict("records")
        if isinstance(previous_context, pd.DataFrame)
        else previous_context
    )

    current = current.copy()
    previous = previous.copy()

    if current.empty:
        current = pd.DataFrame(columns=[
            "station_id",
            "timestamp",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ])

    if previous.empty:
        previous = pd.DataFrame(columns=[
            "station_id",
            "timestamp",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ])

    current["station_id"] = current["station_id"].astype(str)
    previous["station_id"] = previous["station_id"].astype(str)

    current = current.drop_duplicates(
        subset=["station_id"],
        keep="last",
    )
    previous = previous.drop_duplicates(
        subset=["station_id"],
        keep="last",
    )

    merged = current.merge(
        previous,
        on="station_id",
        how="inner",
        suffixes=("_current", "_previous"),
    )

    target_station = str(station_id)

    target = merged[
        merged["station_id"] == target_station
    ]

    network = {}

    for column in value_columns:
        current_col = f"{column}_current"
        previous_col = f"{column}_previous"

        if (
            current_col not in merged.columns
            or previous_col not in merged.columns
        ):
            network[column] = {
                "median_delta": 0.0,
                "median_abs_delta": 0.0,
                "coherence": 0.0,
                "target_delta": None,
            }
            continue

        current_values = pd.to_numeric(
            merged[current_col],
            errors="coerce",
        )

        previous_values = pd.to_numeric(
            merged[previous_col],
            errors="coerce",
        )

        deltas = (
            current_values - previous_values
        ).dropna()

        if deltas.empty:
            network[column] = {
                "median_delta": 0.0,
                "median_abs_delta": 0.0,
                "coherence": 0.0,
                "target_delta": None,
            }
            continue

        median_delta = float(deltas.median())
        median_abs_delta = float(deltas.abs().median())

        target_delta = None

        if not target.empty:
            current_value = _safe_float(
                target.iloc[0][current_col]
            )
            previous_value = _safe_float(
                target.iloc[0][previous_col]
            )

            if (
                current_value is not None
                and previous_value is not None
            ):
                target_delta = (
                    current_value - previous_value
                )

        if abs(median_delta) > 0:
            direction = 1 if median_delta > 0 else -1

            meaningful = deltas[
                deltas.abs()
                >= max(abs(median_delta) * 0.25, 1e-9)
            ]

            if len(meaningful) > 0:
                same_direction = (
                    meaningful > 0
                    if direction > 0
                    else meaningful < 0
                )

                coherence = float(
                    same_direction.mean()
                )
            else:
                coherence = 0.0
        else:
            coherence = 0.0

        network[column] = {
            "median_delta": median_delta,
            "median_abs_delta": median_abs_delta,
            "coherence": _clip01(coherence),
            "target_delta": target_delta,
        }

    # --------------------------------------------------------
    # Explicit data-quality evidence.
    # --------------------------------------------------------

    missing_evidence = 1.0 if any(
        _safe_float(
            features.get(name),
            0,
        ) == 1
        for name in [
            "is_missing_temperature",
            "is_missing_humidity",
            "is_missing_pressure",
        ]
    ) else 0.0

    max_stuck = max(
        _safe_float(
            features.get(
                "temperature_stuck_count"
            ),
            0,
        ),
        _safe_float(
            features.get(
                "humidity_stuck_count"
            ),
            0,
        ),
        _safe_float(
            features.get(
                "pressure_stuck_count"
            ),
            0,
        ),
    )

    frozen_evidence = _clip01(
        max_stuck / 4.0
    )

    physically_implausible = _safe_float(
        features.get(
            "physically_implausible_flag"
        ),
        0,
    )

    physical_evidence = (
        1.0
        if physically_implausible == 1
        else 0.0
    )

    # --------------------------------------------------------
    # Local temporal evidence.
    # --------------------------------------------------------

    temp_z = abs(_safe_float(
        features.get("temperature_zscore_6h"),
        0,
    ))

    humidity_z = abs(_safe_float(
        features.get("humidity_zscore_6h"),
        0,
    ))

    pressure_z = abs(_safe_float(
        features.get("pressure_zscore_6h"),
        0,
    ))

    temporal_z_evidence = _clip01(
        max(
            temp_z / 3.0,
            humidity_z / 3.0,
            pressure_z / 3.0,
        )
    )

    temp_roc_1h = abs(_safe_float(
        features.get("temperature_roc_1h"),
        0,
    ))

    humidity_roc_1h = abs(_safe_float(
        features.get("humidity_roc_1h"),
        0,
    ))

    pressure_roc_1h = abs(_safe_float(
        features.get("pressure_roc_1h"),
        0,
    ))

    drift_evidence = _clip01(
        max(
            temp_roc_1h / 3.0,
            humidity_roc_1h / 15.0,
            pressure_roc_1h / 5.0,
        )
    )

    # --------------------------------------------------------
    # Progressive sensor drift evidence.
    # --------------------------------------------------------

    progressive_drift = 0.0
    directional_consistency_value = 0.0
    persistence_value = 0.0
    persistence_run_length = 0
    cumulative_abnormality_value = 0.0

    if (
        station_history is not None
        and not station_history.empty
        and "timestamp" in station_history.columns
        and "temperature_c" in station_history.columns
    ):
        drift_history = station_history.copy()
        drift_history["timestamp"] = pd.to_datetime(
            drift_history["timestamp"],
            errors="coerce",
        )
        drift_history["temperature_c"] = pd.to_numeric(
            drift_history["temperature_c"],
            errors="coerce",
        )
        drift_history = drift_history.dropna(
            subset=["timestamp", "temperature_c"]
        ).sort_values("timestamp")

        if len(drift_history) >= 10:
            temperatures = drift_history[
                "temperature_c"
            ].to_numpy(dtype=float)
            deltas = np.diff(temperatures)

            recent_delta_count = min(5, len(deltas) - 8)
            historical_deltas = deltas[:-recent_delta_count]
            recent_deltas = deltas[-recent_delta_count:]

            if (
                len(historical_deltas) >= 8
                and len(recent_deltas) >= 3
            ):
                if len(recent_deltas) >= 3:
                    dominant_direction = np.sign(
                        np.sum(recent_deltas)
                    )

                    if dominant_direction == 0:
                        dominant_direction = 1.0
                    directional = (
                        recent_deltas
                        * dominant_direction
                    )
                    supporting = directional > 0
                    directional_count = int(
                        supporting.sum()
                    )

                    directional_consistency = (
                        directional_count
                        / len(recent_deltas)
                    )
                    directional_consistency_value = (
                        directional_consistency
                    )

                    persistence_count = 0
                    for supports_direction in supporting[::-1]:
                        if not supports_direction:
                            break
                        persistence_count += 1

                    persistence = _clip01(
                        persistence_count
                        / len(recent_deltas)
                    )
                    persistence_value = persistence
                    persistence_run_length = persistence_count

                    recent_directional_displacement = float(
                        np.sum(
                            np.abs(
                                recent_deltas[supporting]
                            )
                        )
                    )

                    historical_absolute = np.abs(
                        historical_deltas
                    )
                    expected_windows = []
                    window_size = len(recent_deltas)

                    if len(historical_absolute) >= window_size:
                        for window_start in range(
                            len(historical_absolute)
                            - window_size
                            + 1
                        ):
                            expected_windows.append(
                                float(
                                    np.sum(
                                        historical_absolute[
                                            window_start:
                                            window_start
                                            + window_size
                                        ]
                                    )
                                )
                            )

                    if expected_windows:
                        historical_window_median = float(
                            np.median(expected_windows)
                        )
                        historical_window_mad = float(
                            np.median(
                                np.abs(
                                    np.asarray(expected_windows)
                                    - historical_window_median
                                )
                            )
                        )
                        historical_window_iqr = float(
                            np.percentile(expected_windows, 75)
                            - np.percentile(expected_windows, 25)
                        )
                        robust_window_scale = max(
                            1.4826 * historical_window_mad,
                            historical_window_iqr / 1.349,
                            1e-6,
                        )
                        cumulative_abnormality = _clip01(
                            (
                                recent_directional_displacement
                                - historical_window_median
                            )
                            / robust_window_scale
                        )
                    else:
                        cumulative_abnormality = 0.0

                    cumulative_abnormality_value = (
                        cumulative_abnormality
                    )

                    run_strength = _clip01(
                        (
                            persistence_count - 2
                        )
                        / max(
                            1,
                            len(recent_deltas) - 2,
                        )
                    )

                    persistence_score = _clip01(
                        0.60 * directional_consistency
                        + 0.40 * persistence
                    )

                    network_suppression = _clip01(
                        (
                            1.0
                            - network["temperature_c"][
                                "coherence"
                            ]
                        )
                        / 0.30
                    )

                    progressive_drift = _clip01(
                        (
                            0.35 * persistence_score
                            + 0.65 * cumulative_abnormality
                        )
                        * network_suppression
                        * run_strength
                    )


    # --------------------------------------------------------
    # Regional event evidence.
    #
    # This deliberately uses change across the network rather
    # than absolute station-to-station difference. A regional
    # event can move all stations together while preserving
    # small spatial differences.
    # --------------------------------------------------------

    temp_net = network["temperature_c"]
    humidity_net = network["relative_humidity_pct"]
    pressure_net = network["pressure_hpa"]

    temp_event = (
        abs(temp_net["median_delta"]) >= 3.0
        and temp_net["coherence"] >= 0.70
    )

    humidity_event = (
        abs(humidity_net["median_delta"]) >= 8.0
        and humidity_net["coherence"] >= 0.70
    )

    pressure_event = (
        abs(pressure_net["median_delta"]) >= 3.0
        and pressure_net["coherence"] >= 0.70
    )

    regional_event = (
        (
            int(temp_event)
            + int(humidity_event)
            + int(pressure_event)
        ) >= 1
        and (
            temp_net["coherence"]
            + humidity_net["coherence"]
            + pressure_net["coherence"]
        ) / 3.0 >= 0.70
    )

    network_coherence = _clip01(
        (
            temp_net["coherence"]
            + humidity_net["coherence"]
            + pressure_net["coherence"]
        ) / 3.0
    )

    regional_strengths = []

    if temp_event:
        regional_strengths.append(
            min(
                abs(temp_net["median_delta"]) / 6.0,
                1.0,
            )
        )

    if humidity_event:
        regional_strengths.append(
            min(
                abs(humidity_net["median_delta"]) / 15.0,
                1.0,
            )
        )

    if pressure_event:
        regional_strengths.append(
            min(
                abs(pressure_net["median_delta"]) / 8.0,
                1.0,
            )
        )

    regional_evidence = (
        _clip01(
            max(regional_strengths)
            if regional_strengths
            else 0.0
        )
        * network_coherence
    )

    # --------------------------------------------------------
    # Isolated station evidence.
    # --------------------------------------------------------

    isolation_scores = []

    for variable in value_columns:
        item = network[variable]
        target_delta = item["target_delta"]

        if target_delta is None:
            continue

        network_abs = max(
            item["median_abs_delta"],
            0.25,
        )

        ratio = abs(target_delta) / network_abs

        isolation_scores.append(
            _clip01(
                (ratio - 1.0) / 4.0
            )
        )

    isolation_evidence = (
        max(isolation_scores)
        if isolation_scores
        else 0.0
    )

    local_sensor_evidence = _clip01(
        max(
            isolation_evidence,
            drift_evidence * (
                1.0 - network_coherence
            ),
        )
    )

    sensor_fault_evidence = _clip01(
        max(
            missing_evidence,
            physical_evidence,
            frozen_evidence,
            local_sensor_evidence,
        )
    )

    progressive_sensor_evidence = 0.0

    if (
        progressive_drift >= 0.40
        and isolation_evidence >= 0.40
        and network_coherence < 0.70
    ):
        progressive_sensor_evidence = _clip01(
            0.50 * progressive_drift
            + 0.50 * isolation_evidence
        )

    evidence_anomaly_score = _clip01(
        max(
            regional_evidence,
            sensor_fault_evidence,
            temporal_z_evidence * isolation_evidence,
            progressive_drift,
            progressive_sensor_evidence,
        )
    )

    return {
        "temporal": _clip01(
            max(
                temporal_z_evidence,
                drift_evidence,
            )
        ),
        "spatial": _clip01(
            max(
                regional_evidence,
                isolation_evidence,
            )
        ),
        "multivariate": _clip01(
            max(
                physical_evidence,
                _feature_evidence(
                    features.get(
                        "dew_point_deficit_c"
                    ),
                    scale=5.0,
                ),
            )
        ),
        "data_quality": _clip01(
            max(
                missing_evidence,
                physical_evidence,
            )
        ),
        "frozen_sensor": frozen_evidence,
        "drift": drift_evidence,
        "progressive_drift": _clip01(
            progressive_drift
        ),
        "directional_consistency": _clip01(
            directional_consistency_value
        ),
        "persistence": _clip01(
            persistence_value
        ),
        "persistence_run_length": int(
            persistence_run_length
        ),
        "cumulative_abnormality": _clip01(
            cumulative_abnormality_value
        ),
        "regional_event": regional_evidence,
        "network_coherence": network_coherence,
        "isolation": isolation_evidence,
        "sensor_fault": sensor_fault_evidence,
        "evidence_anomaly_score": evidence_anomaly_score,
        "network_station_count": int(len(current)),
    }


# ============================================================
# RUN REAL RANDOM FOREST MODELS
# ============================================================

def _model_input_row(features: dict):
    return (
        pd.DataFrame([features])
        .reindex(columns=feature_cols)
        .fillna(0)
    )


_ANOMALY_FEATURE_LABELS = {
    "temperature_c": "Temperature",
    "relative_humidity_pct": "Relative humidity",
    "pressure_hpa": "Pressure",
    "temperature_lag_15min": "Temperature lag (15 min)",
    "temperature_lag_1h": "Temperature lag (1 hour)",
    "temperature_lag_3h": "Temperature lag (3 hours)",
    "temperature_roc_15min": "Temperature rate of change (15 min)",
    "temperature_roc_1h": "Temperature rate of change (1 hour)",
    "humidity_lag_15min": "Humidity lag (15 min)",
    "humidity_lag_1h": "Humidity lag (1 hour)",
    "humidity_lag_3h": "Humidity lag (3 hours)",
    "pressure_lag_15min": "Pressure lag (15 min)",
    "pressure_lag_1h": "Pressure lag (1 hour)",
    "pressure_lag_3h": "Pressure lag (3 hours)",
}


def _explain_anomaly_row(row, top_k=8):
    """Return class-1 SHAP contributions for the exact model input row."""
    shap_output = anomaly_explainer.shap_values(
        row,
        check_additivity=False,
    )

    if isinstance(shap_output, list):
        if len(shap_output) <= 1:
            raise ValueError("SHAP output does not contain anomaly class 1.")
        class_values = np.asarray(shap_output[1])
    else:
        values = np.asarray(shap_output)
        if values.ndim == 3:
            if (
                values.shape[0] != 1
                or values.shape[1] != len(feature_cols)
                or values.shape[2] <= 1
            ):
                raise ValueError(
                    f"Unexpected SHAP output shape: {values.shape}"
                )
            class_values = values[0, :, 1]
        elif values.ndim == 2:
            if values.shape != (1, len(feature_cols)):
                raise ValueError(
                    f"Unexpected SHAP output shape: {values.shape}"
                )
            class_values = values[0]
        else:
            raise ValueError(
                f"Unexpected SHAP output shape: {values.shape}"
            )

    class_values = np.asarray(class_values, dtype=float)
    if class_values.shape != (len(feature_cols),):
        raise ValueError(
            f"Unexpected anomaly SHAP vector shape: {class_values.shape}"
        )
    if not np.isfinite(class_values).all():
        raise ValueError("SHAP output contains non-finite values.")

    ranked_indices = np.argsort(-np.abs(class_values))[:top_k]
    items = []
    for index in ranked_indices:
        shap_value = float(class_values[index])
        feature = feature_cols[index]
        value = float(row.iloc[0, index])
        items.append({
            "feature": feature,
            "label": _ANOMALY_FEATURE_LABELS.get(feature, feature),
            "value": value,
            "shap_value": shap_value,
            "abs_shap_value": abs(shap_value),
            "direction": (
                "increases_anomaly"
                if shap_value >= 0
                else "decreases_anomaly"
            ),
        })
    return items


def _run_real_models(
    features: dict,
    evidence: dict | None = None,
    station_id=None,
) -> dict:

    row = _model_input_row(features)

    # --------------------------------------------------------
    # STAGE 1 — existing Random Forest remains primary.
    # --------------------------------------------------------

    anomaly_pred = model_anomaly.predict(row)[0]
    anomaly_proba = model_anomaly.predict_proba(row)[0][1]

    rf_anomaly = bool(
        int(anomaly_pred) == 1
    )

    evidence_score = 0.0
    evidence_anomaly = False
    progressive_drift = 0.0

    isolation = 0.0
    regional = 0.0
    data_quality = 0.0
    frozen_sensor = 0.0
    drift = 0.0
    network_coherence = 0.0
    persistence_run_length = 0
    directional_consistency = 0.0

    if evidence:
        evidence_score = float(
            evidence.get(
                "evidence_anomaly_score",
                0.0,
            )
        )

        isolation = float(
            evidence.get(
                "isolation",
                0.0,
            )
        )

        regional = float(
            evidence.get(
                "regional_event",
                0.0,
            )
        )

        data_quality = float(
            evidence.get(
                "data_quality",
                0.0,
            )
        )

        frozen_sensor = float(
            evidence.get(
                "frozen_sensor",
                0.0,
            )
        )

        drift = float(
            evidence.get(
                "drift",
                0.0,
            )
        )

        network_coherence = float(
            evidence.get(
                "network_coherence",
                0.0,
            )
        )

        progressive_drift = float(
            evidence.get(
                "progressive_drift",
                0.0,
            )
        )

        persistence_run_length = int(
            evidence.get(
                "persistence_run_length",
                0,
            )
        )

        directional_consistency = float(
            evidence.get(
                "directional_consistency",
                0.0,
            )
        )

        # --------------------------------------------------------
        # Persistent regional-state values.
        #
        # These are computed by _calculate_persistent_regional_state
        # and merged into the evidence dict before _run_real_models
        # is called. Reading them here (not recomputing) keeps the
        # evidence pipeline single-pass.
        # --------------------------------------------------------

        regional_state_evidence_val = float(
            evidence.get(
                "regional_state_evidence",
                0.0,
            )
        )

        regional_state_coherence_val = float(
            evidence.get(
                "regional_state_coherence",
                0.0,
            )
        )

        progressive_sensor_evidence = (
            progressive_drift >= 0.60
            and isolation >= 0.35
            and network_coherence < 0.75
        )

        evidence_anomaly = (
            data_quality >= 1.0
            or frozen_sensor >= 1.0
            or (
                regional >= 0.70
                and network_coherence >= 0.70
            )
            or progressive_sensor_evidence
        )

    # --------------------------------------------------------
    # Evidence-corroborated anomaly decision.
    #
    # Random Forest remains the primary detector, but an
    # operational alert requires independent corroboration
    # for live telemetry. This prevents isolated RF false
    # positives from becoming sensor faults.
    # --------------------------------------------------------

    strong_isolation = (
        isolation >= 0.75
    )

    strong_temporal_drift = (
        drift >= 0.80
        and isolation >= 0.75
        and network_coherence < 0.70
    )

    progressive_sensor_evidence = (
        progressive_drift >= 0.60
        and isolation >= 0.35
        and network_coherence < 0.75
    )

    independent_sensor_evidence = (
        strong_isolation
        or strong_temporal_drift
        or progressive_sensor_evidence
    )

    hard_data_quality_failure = (
        data_quality >= 1.0
        or frozen_sensor >= 1.0
    )

    strong_regional_evidence = (
        regional >= 0.70
        and network_coherence >= 0.70
    )

    # --------------------------------------------------------
    # Persistent regional-state direct-anomaly path.
    #
    # A sustained regional weather event (heatwave, cold-spell)
    # does not produce a large short-term Δ-movement signal, so
    # regional_event stays low and strong_regional_evidence does
    # not fire. The RF Stage 1 model, trained on station-level
    # features, also sees the observation as "normal" because the
    # displacement is stable rather than abrupt.
    #
    # regional_state_evidence = regional_state_strength *
    # regional_state_coherence. Requiring both the product AND
    # the coherence fraction to exceed 0.60 means both:
    #   (a) the magnitude of displacement must be significant, AND
    #   (b) a clear majority of the network must share that state.
    # If either is low the product collapses below the threshold.
    #
    # The isolation guard (< 0.50) is the critical safeguard:
    # a sensor fault at a single station produces high isolation
    # regardless of the regional background state. This prevents
    # the persistent-state path from triggering on an isolated
    # hardware fault during a genuine regional event.
    #
    # These thresholds reflect the physical signal semantics;
    # they are not tuned against specific benchmark outcomes.
    # --------------------------------------------------------

    strong_persistent_regional_state = (
        regional_state_evidence_val >= 0.60
        and regional_state_coherence_val >= 0.60
        and isolation < 0.50
    ) if evidence else False

    # Strong, independently-corroborated evidence is conclusive on
    # its own and must not be gated behind the RF model's own vote.
    # Only weak/ambiguous evidence still requires RF corroboration.
    evidence_direct_anomaly = (
        hard_data_quality_failure
        or strong_regional_evidence
        or strong_persistent_regional_state
        or independent_sensor_evidence
    )

    corroborated_rf_anomaly = (
        rf_anomaly
        and evidence_anomaly
    )

    is_anomaly = bool(
        evidence_direct_anomaly
        or corroborated_rf_anomaly
    )

    print(
        "PROGRESSIVE_DECISION",
        {
            "station_id": station_id,
            "progressive_drift": progressive_drift,
            "persistence_run_length": persistence_run_length,
            "directional_consistency": directional_consistency,
            "isolation": isolation,
            "sensor_fault": (
                evidence.get("sensor_fault", 0.0)
                if evidence
                else 0.0
            ),
            "network_temperature_coherence": network_coherence,
            "sensor_drift_evidence": progressive_sensor_evidence,
            "rf_anomaly": rf_anomaly,
            "rf_anomaly_probability": float(anomaly_proba),
            "evidence_anomaly": evidence_anomaly,
            "strong_isolation": strong_isolation,
            "strong_temporal_drift": strong_temporal_drift,
            "final_is_anomaly": is_anomaly,
        },
    )

    anomaly_score = max(
        float(anomaly_proba)
        if is_anomaly
        else 0.0,
        evidence_score
        if (evidence_anomaly or independent_sensor_evidence)
        else 0.0,
    )

    # --------------------------------------------------------
    # STAGE 2 — existing RF, followed by explicit evidence
    # fusion when the network pattern is decisive.
    # --------------------------------------------------------

    weather_or_sensor = "none"
    cause_confidence = None
    rf_cause_confidence = 0.0

    if is_anomaly:

        cause_pred = model_cause.predict(row)[0]
        cause_proba = model_cause.predict_proba(row)[0]

        weather_or_sensor = str(cause_pred)

        rf_cause_confidence = float(
            max(cause_proba)
        )

        cause_confidence = rf_cause_confidence

        if evidence:

            regional = float(
                evidence.get(
                    "regional_event",
                    0.0,
                )
            )

            isolation = float(
                evidence.get(
                    "isolation",
                    0.0,
                )
            )

            sensor_fault = float(
                evidence.get(
                    "sensor_fault",
                    0.0,
                )
            )

            network_coherence = float(
                evidence.get(
                    "network_coherence",
                    0.0,
                )
            )

            if (
                regional >= 0.70
                and network_coherence >= 0.70
            ):
                # Short-term coherent network movement → weather.
                # The network delta is large and spatially coherent;
                # all stations are moving together right now.
                weather_or_sensor = "weather"

                cause_confidence = _clip01(
                    max(
                        rf_cause_confidence,
                        0.70 + 0.30 * regional,
                    )
                )

            elif (
                # --------------------------------------------------------
                # PERSISTENT REGIONAL-STATE → weather override.
                #
                # regional_state_evidence is the PRODUCT of
                # regional_state_strength × regional_state_coherence.
                # Both magnitude and network-wide participation must be
                # jointly present (the product collapses if either is low).
                #
                # The isolation guard is the critical general safeguard:
                # a sensor fault at a single station will have high
                # isolation regardless of background regional state.
                # Requiring isolation < 0.50 means this branch can only
                # fire when the target station is NOT singled out
                # relative to its peers — i.e., it shares the displaced
                # state with the network.
                #
                # This is deliberately independent of regional_event.
                # regional_event detects short-term coherent movement;
                # regional_state_evidence detects persistent displacement
                # from each station's own historical baseline, which is
                # the correct signal for sustained heatwaves/cold-spells
                # where the network is stable-but-displaced (Δ near zero,
                # absolute displacement large).
                # --------------------------------------------------------
                float(
                    evidence.get(
                        "regional_state_evidence",
                        0.0,
                    )
                ) >= 0.60
                and float(
                    evidence.get(
                        "regional_state_coherence",
                        0.0,
                    )
                ) >= 0.60
                and isolation < 0.50
            ):
                regional_state_evidence_val = float(
                    evidence.get(
                        "regional_state_evidence",
                        0.0,
                    )
                )

                weather_or_sensor = "weather"

                cause_confidence = _clip01(
                    max(
                        rf_cause_confidence,
                        0.60 + 0.40 * regional_state_evidence_val,
                    )
                )

            elif (
                (
                    sensor_fault >= 0.70
                    and (
                        isolation >= 0.50
                        or evidence.get(
                            "data_quality",
                            0.0,
                        ) >= 1.0
                        or evidence.get(
                            "frozen_sensor",
                            0.0,
                        ) >= 1.0
                        or evidence.get(
                            "drift",
                            0.0,
                        ) >= 0.70
                    )
                )
                or progressive_sensor_evidence
            ):
                weather_or_sensor = "sensor"

                cause_confidence = _clip01(
                    max(
                        rf_cause_confidence,
                        0.70 + 0.30 * sensor_fault,
                    )
                )

    # --------------------------------------------------------
    # Root-cause component.
    # --------------------------------------------------------

    z_scores = {
        "temperature": abs(
            _safe_float(
                features.get(
                    "temperature_zscore_6h"
                ),
                0,
            )
        ),
        "humidity": abs(
            _safe_float(
                features.get(
                    "humidity_zscore_6h"
                ),
                0,
            )
        ),
        "pressure": abs(
            _safe_float(
                features.get(
                    "pressure_zscore_6h"
                ),
                0,
            )
        ),
    }

    fault_component = "none"

    if (
        is_anomaly
        and weather_or_sensor.lower() == "sensor"
    ):
        fault_component = max(
            z_scores,
            key=z_scores.get,
        )

        if evidence:
            if evidence.get("data_quality", 0.0) >= 1.0:
                fault_component = "data_quality"
            elif evidence.get("frozen_sensor", 0.0) >= 1.0:
                fault_component = "sensor"
            elif evidence.get("drift", 0.0) >= 0.70:
                fault_component = "temperature"

    return {
        "anomaly": is_anomaly,
        "anomaly_score": round(
            float(anomaly_score),
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
        "evidence":
            evidence or {},
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

def _calculate_persistent_regional_state(
    current_context: pd.DataFrame,
    historical_context: pd.DataFrame,
    current_timestamp=None,
) -> dict:
    """
    Detect persistent regional-state evidence.

    This is deliberately separate from regional_event.

    regional_event:
        Short-term coherent network movement.

    regional_state_evidence:
        Current network state persistently displaced from
        each station's own historical baseline.
    """

    empty_result = {
        "regional_state_strength": 0.0,
        "regional_state_coherence": 0.0,
        "regional_state_evidence": 0.0,
    }

    if (
        current_context is None
        or current_context.empty
        or historical_context is None
        or historical_context.empty
    ):
        return empty_result

    required_columns = [
        "station_id",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]

    history_columns = [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]

    if any(
        column not in current_context.columns
        for column in required_columns
    ):
        return empty_result

    if any(
        column not in historical_context.columns
        for column in history_columns
    ):
        return empty_result

    current = current_context[
        required_columns
    ].copy()

    history = historical_context[
        history_columns
    ].copy()

    current["station_id"] = (
        current["station_id"]
        .astype(str)
    )

    history["station_id"] = (
        history["station_id"]
        .astype(str)
    )

    numeric_columns = required_columns[1:]

    for column in numeric_columns:
        current[column] = pd.to_numeric(
            current[column],
            errors="coerce",
        )

        history[column] = pd.to_numeric(
            history[column],
            errors="coerce",
        )

    current = current.dropna(
        subset=numeric_columns
    )

    history = history.dropna(
        subset=numeric_columns
    )

    # Never allow observations at or after the observation being
    # evaluated to influence the historical baseline. This matters
    # especially for controlled simulator timestamps because the
    # database can contain benchmark history from later dates.
    if current_timestamp is not None and not history.empty:
        evaluation_timestamp = pd.to_datetime(
            current_timestamp,
            errors="coerce",
            utc=True,
        )

        if pd.notna(evaluation_timestamp):
            history["timestamp"] = pd.to_datetime(
                history["timestamp"],
                errors="coerce",
                utc=True,
            )

            history = history[
                history["timestamp"] < evaluation_timestamp
            ]

    if len(current) < 5 or history.empty:
        return empty_result

    # --------------------------------------------------------
    # Station-specific historical baseline.
    #
    # Median is used instead of mean so that isolated spikes,
    # drops and jumps do not substantially distort the baseline.
    # --------------------------------------------------------

    baseline = (
        history
        .groupby("station_id")[
            numeric_columns
        ]
        .median()
        .reset_index()
    )

    merged = current.merge(
        baseline,
        on="station_id",
        how="inner",
        suffixes=(
            "_current",
            "_baseline",
        ),
    )

    if len(merged) < 5:
        return empty_result

    # --------------------------------------------------------
    # Current displacement from station baseline.
    #
    # These are evidence scaling factors, not anomaly
    # thresholds.
    # --------------------------------------------------------

    temperature_displacement = (
        (
            merged["temperature_c_current"]
            - merged["temperature_c_baseline"]
        ).abs()
        / 4.0
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    humidity_displacement = (
        (
            merged["relative_humidity_pct_current"]
            - merged["relative_humidity_pct_baseline"]
        ).abs()
        / 15.0
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    pressure_displacement = (
        (
            merged["pressure_hpa_current"]
            - merged["pressure_hpa_baseline"]
        ).abs()
        / 8.0
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    # --------------------------------------------------------
    # Composite station-state displacement.
    #
    # Temperature + humidity carry most of the persistent
    # thermal-state signal. Pressure remains supporting
    # evidence.
    # --------------------------------------------------------

    station_strength = (
        0.50 * temperature_displacement
        + 0.35 * humidity_displacement
        + 0.15 * pressure_displacement
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    regional_state_strength = float(
        station_strength.median()
    )

    # Fraction of stations showing meaningful persistent
    # displacement.
    regional_state_coherence = _clip01(
        float(
            (
                station_strength >= 0.35
            ).mean()
        )
    )

    # Both magnitude and participation must be present.
    regional_state_evidence = _clip01(
        regional_state_strength
        * regional_state_coherence
    )

    return {
        "regional_state_strength":
            _clip01(regional_state_strength),

        "regional_state_coherence":
            _clip01(regional_state_coherence),

        "regional_state_evidence":
            _clip01(regional_state_evidence),
    }

def _build_live_prediction_context(
    reading: RawTelemetry,
    spatial_context: pd.DataFrame | None = None,
    persistent_history_context: pd.DataFrame | None = None,
):
    current_timestamp = _normalize_ingest_timestamp(
        reading.timestamp
    )

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

    if spatial_context is None:
        spatial_rows = get_latest_station_context(
            timestamp=current_timestamp,
            max_age_seconds=1800,
        )

        all_station_history = _context_dataframe(
            spatial_rows
        )

    else:
        all_station_history = _context_dataframe(
            spatial_context.to_dict("records")
            if isinstance(spatial_context, pd.DataFrame)
            else spatial_context
        )

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

    all_station_history = all_station_history[
        all_station_history["station_id"].astype(str)
        != str(reading.station_id)
    ]

    current_spatial_row = pd.DataFrame([
        {
            "station_id": reading.station_id,
            "timestamp": current_timestamp,
            "temperature_c": reading.temperature_c,
            "relative_humidity_pct":
                reading.relative_humidity_pct,
            "pressure_hpa": reading.pressure_hpa,
        }
    ])

    all_station_history = pd.concat(
        [
            all_station_history,
            current_spatial_row,
        ],
        ignore_index=True,
    )

    # --------------------------------------------------------
    # Persistent regional-state context.
    #
    # Fetch bounded recent history for every station present in
    # the contemporaneous network snapshot. For /ingest/batch,
    # the caller supplies this dataframe once so the same
    # history is reused for every station.
    # --------------------------------------------------------

    if persistent_history_context is None:
        persistent_station_ids = (
            all_station_history["station_id"]
            .astype(str)
            .drop_duplicates()
            .tolist()
        )

        persistent_history_context = pd.DataFrame(
            get_station_feature_history_batch(
                persistent_station_ids,
                limit=672,
            )
        )

    if persistent_history_context is None:
        persistent_history_context = pd.DataFrame()

    features = build_features(
        station_id=reading.station_id,
        timestamp=current_timestamp,
        temperature_c=reading.temperature_c,
        relative_humidity_pct=reading.relative_humidity_pct,
        pressure_hpa=reading.pressure_hpa,
        history=history,
        all_station_history=all_station_history,
    )

    previous_context = _previous_network_context(
        current_timestamp
    )

    evidence = _calculate_network_evidence(
        station_id=reading.station_id,
        timestamp=current_timestamp,
        current_context=all_station_history,
        previous_context=previous_context,
        features=features,
        station_history=pd.concat(
            [
                history,
                pd.DataFrame([{
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
                }]),
            ],
            ignore_index=True,
        ),
    )

    # --------------------------------------------------------
    # Add persistent regional-state evidence as a parallel
    # signal. Existing short-term regional_event and
    # network_coherence semantics remain untouched.
    #
    # This phase intentionally exposes the new signal without
    # changing the anomaly fusion decision in _run_real_models.
    # --------------------------------------------------------

    persistent_regional_state = _calculate_persistent_regional_state(
        current_context=all_station_history,
        historical_context=persistent_history_context,
        current_timestamp=current_timestamp,
    )

    evidence.update(
        persistent_regional_state
    )

    return current_timestamp, features, evidence


def _process_live_reading(
    reading: RawTelemetry,
    spatial_context: pd.DataFrame | None = None,
    persistent_history_context: pd.DataFrame | None = None,
):
    """
    Build the canonical 50-feature vector and run the real
    two-stage ML pipeline.

    Random Forest remains the primary ML detector. The evidence
    layer supplements it with explicit temporal, spatial,
    network-coherence, frozen, missing and physical evidence.
    """

    current_timestamp, features, evidence = _build_live_prediction_context(
        reading,
        spatial_context=spatial_context,
        persistent_history_context=persistent_history_context,
    )

    model_result = _run_real_models(
        features,
        evidence=evidence,
        station_id=reading.station_id,
    )

    return {
        "station_id": reading.station_id,
        "timestamp": current_timestamp.isoformat(),
        "temperature_c": reading.temperature_c,
        "relative_humidity_pct":
            reading.relative_humidity_pct,
        "pressure_hpa": reading.pressure_hpa,
        "anomaly": model_result["anomaly"],
        "anomaly_score":
            model_result["anomaly_score"],
        "weather_or_sensor":
            model_result["weather_or_sensor"],
        "confidence":
            model_result["confidence"],
        "fault_component":
            model_result["fault_component"],
        "evidence":
            model_result["evidence"],
        "features_computed_count":
            len(features),
    }


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
        # Fetch persistent regional-state history once for the
        # complete batch and reuse it for every station.
        # This avoids 20 identical seven-day history queries.
        # ----------------------------------------------------

        persistent_history_context = pd.DataFrame(
            get_station_feature_history_batch(
                station_ids,
                limit=672,
            )
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
                persistent_history_context=persistent_history_context,
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

        anomaly_pred = model_anomaly.predict(row)[0]
        anomaly_proba = model_anomaly.predict_proba(row)[0][1]

        is_anomaly = bool(
            int(anomaly_pred) == 1
        )

        weather_or_sensor = "none"
        cause_confidence = None

        if is_anomaly:

            cause_pred = model_cause.predict(row)[0]
            cause_proba = model_cause.predict_proba(row)[0]

            weather_or_sensor = str(cause_pred)
            cause_confidence = float(
                max(cause_proba)
            )

        data_quality = 1.0 if any(
            _safe_float(
                f.get(name),
                0,
            ) == 1
            for name in [
                "is_missing_temperature",
                "is_missing_humidity",
                "is_missing_pressure",
            ]
        ) else 0.0

        frozen_sensor = _clip01(
            max(
                _safe_float(
                    f.get(
                        "temperature_stuck_count"
                    ),
                    0,
                ),
                _safe_float(
                    f.get(
                        "humidity_stuck_count"
                    ),
                    0,
                ),
                _safe_float(
                    f.get(
                        "pressure_stuck_count"
                    ),
                    0,
                ),
            ) / 4.0
        )

        physical = (
            1.0
            if _safe_float(
                f.get(
                    "physically_implausible_flag"
                ),
                0,
            ) == 1
            else 0.0
        )

        if (
            data_quality >= 1.0
            or frozen_sensor >= 1.0
            or physical >= 1.0
        ):
            is_anomaly = True
            anomaly_proba = max(
                float(anomaly_proba),
                0.80,
            )
            weather_or_sensor = "sensor"
            cause_confidence = max(
                float(cause_confidence or 0.0),
                0.80,
            )

        fault_component = "none"

        if (
            is_anomaly
            and weather_or_sensor == "sensor"
        ):

            z_scores = {
                "temperature": abs(
                    _safe_float(
                        f.get(
                            "temperature_zscore_6h"
                        ),
                        0,
                    )
                ),
                "humidity": abs(
                    _safe_float(
                        f.get(
                            "humidity_zscore_6h"
                        ),
                        0,
                    )
                ),
                "pressure": abs(
                    _safe_float(
                        f.get(
                            "pressure_zscore_6h"
                        ),
                        0,
                    )
                ),
            }

            fault_component = max(
                z_scores,
                key=z_scores.get,
            )

            if data_quality >= 1.0 or physical >= 1.0:
                fault_component = "data_quality"
            elif frozen_sensor >= 1.0:
                fault_component = "sensor"

        return {
            "station_id":
                str(reading.station_id),
            "timestamp":
                str(reading.timestamp),
            "temperature_c":
                f.get("temperature_c"),
            "relative_humidity_pct":
                f.get("relative_humidity_pct"),
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
                    _feature_evidence(
                        f.get(
                            "temperature_zscore_6h"
                        ),
                        scale=3.0,
                    ),
                "spatial":
                    _feature_evidence(
                        f.get(
                            "regional_temp_zscore"
                        ),
                        scale=3.0,
                    ),
                "multivariate":
                    physical,
                "data_quality":
                    data_quality,
                "frozen_sensor":
                    frozen_sensor,
                "drift":
                    _clip01(
                        max(
                            abs(
                                _safe_float(
                                    f.get(
                                        "temperature_roc_1h"
                                    ),
                                    0,
                                )
                            ) / 3.0,
                            abs(
                                _safe_float(
                                    f.get(
                                        "humidity_roc_1h"
                                    ),
                                    0,
                                )
                            ) / 15.0,
                            abs(
                                _safe_float(
                                    f.get(
                                        "pressure_roc_1h"
                                    ),
                                    0,
                                )
                            ) / 5.0,
                        )
                    ),
                "regional_event": 0.0,
                "network_coherence": 0.0,
                "isolation": 0.0,
                "sensor_fault":
                    max(
                        data_quality,
                        frozen_sensor,
                        physical,
                    ),
                "evidence_anomaly_score": 0.0,
                "network_station_count": 0,
            },
        }

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
        # Timestamp and station identity.
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

        current_timestamp = pd.to_datetime(
            raw_row.get("timestamp")
        )

        if current_timestamp.tzinfo is None:
            current_timestamp = current_timestamp.tz_localize(
                "Asia/Kolkata"
            )
        else:
            current_timestamp = current_timestamp.tz_convert(
                "Asia/Kolkata"
            )

        # ----------------------------------------------------
        # Generate the same network evidence used by /ingest.
        # ----------------------------------------------------

        history = pd.DataFrame(
            get_station_feature_history(
                station_id=source_station,
                before_timestamp=current_timestamp,
                limit=96,
            )
        )

        station_context = get_latest_station_context(
            timestamp=current_timestamp,
            max_age_seconds=1800,
        )

        all_station_history = pd.DataFrame(
            station_context
        )

        if (
            not all_station_history.empty
            and "station_id" in all_station_history.columns
        ):
            all_station_history = all_station_history[
                all_station_history["station_id"].astype(str)
                != source_station
            ]

        current_context = pd.DataFrame(
            [
                {
                    "station_id": source_station,
                    "timestamp": current_timestamp,
                    "temperature_c": raw_row.get(
                        "temperature_c"
                    ),
                    "relative_humidity_pct": raw_row.get(
                        "relative_humidity_pct"
                    ),
                    "pressure_hpa": raw_row.get(
                        "pressure_hpa"
                    ),
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

        persistent_station_ids = (
            all_station_history["station_id"]
            .astype(str)
            .drop_duplicates()
            .tolist()
        )

        persistent_history_context = pd.DataFrame(
            get_station_feature_history_batch(
                persistent_station_ids,
                limit=672,
            )
        )

        previous_context = _previous_network_context(
            current_timestamp
        )

        evidence = _calculate_network_evidence(
            station_id=source_station,
            timestamp=current_timestamp,
            current_context=all_station_history,
            previous_context=previous_context,
            features=features,
            station_history=pd.concat(
                [
                    history,
                    current_context,
                ],
                ignore_index=True,
            ),
        )

        persistent_regional_state = _calculate_persistent_regional_state(
            current_context=all_station_history,
            historical_context=persistent_history_context,
            current_timestamp=current_timestamp,
        )

        evidence.update(
            persistent_regional_state
        )

        # ----------------------------------------------------
        # Run actual ML pipeline with network evidence.
        # ----------------------------------------------------

        prediction = _run_real_models(
            features,
            evidence=evidence,
            station_id=source_station,
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

@app.get("/model/status")
def model_status():
    """Return metadata from the actual loaded ML model artifacts.

    Accuracy and F1 are reported as unavailable because the current
    backend does not persist a formal evaluation artifact containing
    those metrics. No fabricated validation numbers are returned.
    """
    return {
        "stage1": {
            "name": "Stage 1 Anomaly Gatekeeper",
            "algorithm": "Random Forest Classifier",
            "status": "Loaded",
            "version": "model_anomaly_detector.pkl",
            "featuresCount": int(getattr(model_anomaly, "n_features_in_", 0)),
            "trainingPeriod": "Synthetic AWS telemetry dataset",
            "evaluationPeriod": "Not persisted in model artifact",
            "lastTrained": "Not available from model artifact",
            "accuracy": "Not available",
            "f1Score": "Not available",
        },
        "stage2": {
            "name": "Stage 2 Root-Cause Attribution",
            "algorithm": "Random Forest Classifier",
            "status": "Loaded",
            "version": "model_weather_or_sensor.pkl",
            "featuresCount": int(getattr(model_cause, "n_features_in_", 0)),
            "trainingPeriod": "Synthetic AWS telemetry dataset",
            "evaluationPeriod": "Not persisted in model artifact",
            "lastTrained": "Not available from model artifact",
            "accuracy": "Not available",
            "f1Score": "Not available",
        },
    }


def _baseline_stats(values):
    """Return median and MAD for finite numeric values."""
    numeric_values = [
        float(value)
        for value in values
        if value is not None and np.isfinite(value)
    ]

    if not numeric_values:
        return {
            "median": None,
            "mad": None,
        }

    median = float(np.median(numeric_values))
    mad = float(np.median(np.abs(np.asarray(numeric_values) - median)))

    return {
        "median": median,
        "mad": mad,
    }


def _baseline_metrics(rows):
    return {
        "temperature_c": _baseline_stats(
            row["temperature_c"] for row in rows
        ),
        "relative_humidity_pct": _baseline_stats(
            row["relative_humidity_pct"] for row in rows
        ),
        "pressure_hpa": _baseline_stats(
            row["pressure_hpa"] for row in rows
        ),
    }


def _health_clip(value):
    if value is None:
        return None
    return float(max(0.0, min(1.0, float(value))))


def _health_score_from_penalty(penalty):
    if penalty is None:
        return None
    return int(round(100.0 * (1.0 - _health_clip(penalty))))


def _health_status(score):
    if score is None:
        return "Insufficient Data"
    if score >= 90:
        return "Healthy"
    if score >= 75:
        return "Watch"
    if score >= 50:
        return "Degraded"
    return "Critical"


def _health_numeric(value, default=0.0):
    numeric = _safe_float(value, default)
    return float(numeric) if numeric is not None else float(default)


def _health_timestamp(value):
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("Asia/Kolkata")
    return timestamp


def _health_channel(
    current_value,
    drift,
    stuck_count,
    missing,
    spatial_deviation,
    physical_penalty=0.0,
    temporal_context_factor=1.0,
):
    """Build a prototype operational channel index, not failure probability."""
    usable = current_value is not None and not pd.isna(current_value)
    if not usable:
        return {
            "score": None,
            "status": "Insufficient Data",
            "signals": {
                "drift": _health_clip(drift),
                "stuck_count": int(max(0, round(_health_numeric(stuck_count)))),
                "missing": 1.0,
                "spatial_deviation": _health_clip(spatial_deviation),
            },
        }

    # The temporal, frozen, and spatial terms are overlap groups. Each
    # group contributes once, preventing ROC/z-score/stuck signals from
    # independently double-counting the same physical failure.
    temporal_penalty = _health_clip(
        _health_numeric(drift) * temporal_context_factor
    )
    frozen_penalty = _health_clip(_health_numeric(stuck_count) / 4.0)
    spatial_penalty = _health_clip(spatial_deviation)
    penalty = (
        0.45 * temporal_penalty
        + 0.30 * frozen_penalty
        + 0.15 * spatial_penalty
        + 0.10 * _health_clip(physical_penalty)
        + 0.20 * _health_clip(missing)
    )
    penalty = min(1.0, penalty)
    score = _health_score_from_penalty(penalty)
    return {
        "score": score,
        "status": _health_status(score),
        "signals": {
            "drift": _health_clip(drift),
            "stuck_count": int(max(0, round(_health_numeric(stuck_count)))),
            "missing": _health_clip(missing),
            "spatial_deviation": _health_clip(spatial_deviation),
        },
    }


def _health_explanations(
    channels,
    drift,
    sensor_fault,
    isolation,
    frozen,
    physical,
    missing_rate,
    timestamp_gap,
    network_coherence,
    neighbor_agreement,
    anomalies_24h,
    anomalies_7d,
):
    explanations = []
    channel_names = {
        "temperature": "Temperature",
        "humidity": "Humidity",
        "pressure": "Pressure",
    }
    for name, channel in channels.items():
        if channel["status"] in {"Degraded", "Critical", "Watch"}:
            signal = channel["signals"]
            if signal["stuck_count"] >= 2:
                explanations.append(
                    f"{channel_names[name]} channel shows repeated identical readings."
                )
            elif signal["drift"] >= 0.70:
                explanations.append(
                    f"{channel_names[name]} channel shows elevated recent drift."
                )
            elif signal["spatial_deviation"] >= 0.50:
                explanations.append(
                    f"{channel_names[name]} channel differs from its contemporaneous neighbor."
                )
    if frozen >= 0.70:
        explanations.append("Sensor history shows strong frozen/stuck evidence.")
    if isolation >= 0.50:
        explanations.append("Telemetry is isolated from contemporaneous neighbor movement.")
    if physical >= 1.0:
        explanations.append("Telemetry contains a physical-consistency violation.")
    if missing_rate > 0:
        explanations.append("Recent telemetry contains missing channel values.")
    if timestamp_gap > 0:
        explanations.append("Recent telemetry contains timestamp gaps.")
    if network_coherence >= 0.70 and sensor_fault < 0.70:
        explanations.append(
            "Strong network coherence provides regional context and reduces evidence of isolated hardware fault."
        )
    elif neighbor_agreement >= 0.70:
        explanations.append("Telemetry agrees with the contemporaneous neighbor.")
    if anomalies_24h > 0:
        explanations.append(
            f"{anomalies_24h} persisted live anomaly record(s) occurred in the last 24 hours."
        )
    elif anomalies_7d > 0:
        explanations.append(
            f"{anomalies_7d} persisted live anomaly record(s) occurred in the last 7 days."
        )
    return explanations[:5]


def _calculate_station_health(
    station_id,
    history_rows,
    anomaly_rows,
    current_context=None,
    previous_context=None,
    now=None,
):
    history = pd.DataFrame(history_rows or [])
    if history.empty:
        return {
            "station_id": station_id,
            "timestamp": None,
            "overall": {"score": None, "status": "Insufficient Data"},
            "channels": {
                name: {"score": None, "status": "Insufficient Data", "signals": {}}
                for name in ("temperature", "humidity", "pressure")
            },
            "drift": {
                "score": None,
                "progressive": None,
                "directional_consistency": None,
                "persistence": None,
                "run_length": 0,
            },
            "sensor_fault": {
                "score": None,
                "isolation": None,
                "frozen": None,
                "physical_consistency": None,
            },
            "data_quality": {
                "missing_rate": None,
                "timestamp_gap": None,
                "observation_age_seconds": None,
            },
            "network": {"coherence": None, "neighbor_agreement": None},
            "anomaly_burden": {"anomalies_24h": 0, "anomalies_7d": 0},
            "explanation": ["Insufficient telemetry history for station health."],
            "data_sufficiency": {"status": "insufficient", "samples_used": 0},
        }

    now = _health_timestamp(now or pd.Timestamp.now(tz="Asia/Kolkata"))
    history["timestamp"] = history["timestamp"].map(_health_timestamp)
    history = history.dropna(subset=["timestamp"]).sort_values("timestamp")
    latest = history.iloc[-1]
    usable = history[
        history[["temperature_c", "relative_humidity_pct", "pressure_hpa"]]
        .notna()
        .any(axis=1)
    ]
    if usable.empty:
        return _calculate_station_health(station_id, [], anomaly_rows, now)

    current_timestamp = latest["timestamp"]
    recent = usable.tail(96)
    samples_used = len(recent)
    quality_window = history.tail(96)
    complete_fields = quality_window[
        ["temperature_c", "relative_humidity_pct", "pressure_hpa"]
    ].notna().sum().sum()
    total_fields = max(1, len(quality_window) * 3)
    missing_rate = 1.0 - (complete_fields / total_fields)
    if samples_used >= 96:
        sufficiency = "high"
    elif samples_used >= 24:
        sufficiency = "medium"
    elif samples_used >= 8:
        sufficiency = "low"
    else:
        sufficiency = "insufficient"

    gaps = quality_window["timestamp"].diff().dt.total_seconds().dropna()
    timestamp_gap = float(
        (gaps.sub(900).abs() > 1e-6).any()
    ) if not gaps.empty else 0.0
    age_seconds = max(0.0, (now - current_timestamp).total_seconds())

    if current_context is None:
        current_context = get_latest_station_context(current_timestamp)
    context = pd.DataFrame(current_context or [])
    if context.empty:
        context = history[[
            "station_id", "timestamp", "temperature_c",
            "relative_humidity_pct", "pressure_hpa",
        ]].tail(20)

    reading = RawTelemetry(
        station_id=station_id,
        timestamp=current_timestamp.isoformat(),
        temperature_c=latest.get("temperature_c"),
        relative_humidity_pct=latest.get("relative_humidity_pct"),
        pressure_hpa=latest.get("pressure_hpa"),
    )
    features = build_features(
        station_id=station_id,
        timestamp=current_timestamp,
        temperature_c=reading.temperature_c,
        relative_humidity_pct=reading.relative_humidity_pct,
        pressure_hpa=reading.pressure_hpa,
        history=recent,
        all_station_history=context,
    )
    evidence = _calculate_network_evidence(
        station_id=station_id,
        timestamp=current_timestamp,
        current_context=context,
        previous_context=(
            previous_context
            if previous_context is not None
            else _previous_network_context(current_timestamp)
        ),
        features=features,
        station_history=recent,
    )

    sensor_fault_score = _health_clip(evidence.get("sensor_fault", 0.0))
    physical = 1.0 if _health_numeric(
        features.get("physically_implausible_flag"),
    ) == 1.0 else 0.0
    isolation = _health_clip(evidence.get("isolation", 0.0))
    frozen = _health_clip(evidence.get("frozen_sensor", 0.0))
    coherence = _health_clip(evidence.get("network_coherence", 0.0))

    field_config = {
        "temperature": ("temperature_c", "temperature_roc_1h", "temperature_stuck_count", "spatial_temp_diff"),
        "humidity": ("relative_humidity_pct", "humidity_roc_1h", "humidity_stuck_count", "spatial_humidity_diff"),
        "pressure": ("pressure_hpa", "pressure_roc_1h", "pressure_stuck_count", "spatial_pressure_diff"),
    }
    channels = {}
    for name, (value_key, drift_key, stuck_key, spatial_key) in field_config.items():
        spatial = _health_numeric(features.get(spatial_key), 0.0)
        raw_drift = abs(_health_numeric(features.get(drift_key), 0.0)) / {
            "temperature": 3.0,
            "humidity": 15.0,
            "pressure": 5.0,
        }[name]
        temporal_context_factor = (
            1.0
            if (
                raw_drift >= 0.70
                and (
                    isolation >= 0.75
                    or _health_numeric(evidence.get("progressive_drift")) >= 0.80
                )
            )
            else 0.0
        )
        channels[name] = _health_channel(
            latest.get(value_key),
            raw_drift,
            features.get(stuck_key),
            1.0 if pd.isna(latest.get(value_key)) else 0.0,
            min(1.0, abs(spatial) / {"temperature": 5.0, "humidity": 20.0, "pressure": 8.0}[name]),
            physical_penalty=(
                1.0
                if _health_numeric(
                    features.get("physically_implausible_flag"),
                ) == 1.0
                else 0.0
            ),
            temporal_context_factor=temporal_context_factor,
        )

    drift_score = _health_clip(max(
        evidence.get("drift", 0.0),
        evidence.get("progressive_drift", 0.0),
    ))
    neighbor_agreement = _health_clip(1.0 - isolation)

    valid_scores = [channel["score"] for channel in channels.values() if channel["score"] is not None]
    health_sensor_fault = (
        sensor_fault_score
        if (
            sensor_fault_score >= 0.75
            or frozen >= 0.70
            or physical >= 1.0
            or _health_numeric(evidence.get("progressive_drift")) >= 0.80
        )
        else 0.0
    )
    if sufficiency == "insufficient" or not valid_scores:
        overall_score = None
    else:
        overall_penalty = (
            0.55 * (1.0 - min(valid_scores) / 100.0)
            + 0.25 * health_sensor_fault
            + 0.10 * missing_rate
            + 0.10 * min(1.0, len(anomaly_rows) / 5.0)
        )
        # Coherent network movement is context, not a hardware penalty.
        if coherence >= 0.70 and isolation < 0.50:
            overall_penalty *= 0.75
        overall_score = _health_score_from_penalty(overall_penalty)

    cutoff_24h = current_timestamp - pd.Timedelta(hours=24)
    cutoff_7d = current_timestamp - pd.Timedelta(days=7)
    anomaly_timestamps = [
        _health_timestamp(row.get("timestamp"))
        for row in anomaly_rows
    ]
    anomalies_24h = sum(ts is not None and ts >= cutoff_24h for ts in anomaly_timestamps)
    anomalies_7d = sum(ts is not None and ts >= cutoff_7d for ts in anomaly_timestamps)
    explanations = _health_explanations(
        channels,
        drift_score,
        sensor_fault_score,
        isolation,
        frozen,
        physical,
        missing_rate,
        timestamp_gap,
        coherence,
        neighbor_agreement,
        anomalies_24h,
        anomalies_7d,
    )
    return {
        "station_id": station_id,
        "timestamp": current_timestamp.isoformat(),
        "overall": {"score": overall_score, "status": _health_status(overall_score)},
        "channels": channels,
        "drift": {
            "score": drift_score,
            "progressive": _health_clip(evidence.get("progressive_drift", 0.0)),
            "directional_consistency": _health_clip(evidence.get("directional_consistency", 0.0)),
            "persistence": _health_clip(evidence.get("persistence", 0.0)),
            "run_length": int(evidence.get("persistence_run_length", 0)),
        },
        "sensor_fault": {
            "score": sensor_fault_score,
            "isolation": isolation,
            "frozen": frozen,
            "physical_consistency": physical,
        },
        "data_quality": {
            "missing_rate": _health_clip(missing_rate),
            "timestamp_gap": timestamp_gap,
            "observation_age_seconds": age_seconds,
        },
        "network": {
            "coherence": coherence,
            "neighbor_agreement": neighbor_agreement,
        },
        "anomaly_burden": {
            "anomalies_24h": int(anomalies_24h),
            "anomalies_7d": int(anomalies_7d),
        },
        "explanation": explanations or ["No elevated health signal was observed."],
        "data_sufficiency": {
            "status": sufficiency,
            "samples_used": int(samples_used),
        },
    }


@app.get("/station/{station_id}/baseline")
def station_baseline(station_id: str):
    """Return a read-only robust baseline from same-station telemetry."""
    known_station_ids = set(
        stations_df["station_id"].astype(str)
    )

    if station_id not in known_station_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown station: {station_id}",
        )

    # Seven days at a 15-minute cadence is the maximum local history used
    # here. It is a bounded recent baseline, not multi-year climatology.
    history_rows = get_station_feature_history(
        station_id,
        limit=672,
    )

    usable_rows = []
    for row in history_rows or []:
        timestamp = pd.to_datetime(
            row.get("timestamp"),
            errors="coerce",
            utc=True,
        )
        if pd.isna(timestamp):
            continue

        values = {}
        for field in (
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ):
            value = row.get(field)
            try:
                values[field] = (
                    float(value)
                    if value is not None and np.isfinite(float(value))
                    else None
                )
            except (TypeError, ValueError):
                values[field] = None

        if any(value is not None for value in values.values()):
            usable_rows.append(
                {
                    **values,
                    "timestamp": timestamp,
                }
            )

    latest_timestamp = (
        max(row["timestamp"] for row in usable_rows)
        if usable_rows
        else None
    )

    time_of_day_rows = []
    if latest_timestamp is not None:
        latest_bucket = (
            latest_timestamp.hour * 4
            + latest_timestamp.minute // 15
        )
        time_of_day_rows = [
            row
            for row in usable_rows
            if (
                row["timestamp"].hour * 4
                + row["timestamp"].minute // 15
            ) == latest_bucket
        ]

    sample_count = len(usable_rows)
    time_of_day_sample_count = len(time_of_day_rows)

    # Quality is deliberately deterministic: high requires 48 usable
    # observations and 4 same-time-bucket observations; medium requires
    # 8 usable observations and 2 same-time-bucket observations.
    if sample_count >= 48 and time_of_day_sample_count >= 4:
        baseline_quality = "high"
    elif sample_count >= 8 and time_of_day_sample_count >= 2:
        baseline_quality = "medium"
    else:
        baseline_quality = "insufficient"

    if baseline_quality == "insufficient":
        explanation = (
            "Insufficient same-station history for a reliable robust "
            "baseline; no multi-year seasonal climatology is available."
        )
    elif baseline_quality == "medium":
        explanation = (
            "Limited same-station history supports a usable robust baseline, "
            "but it is not a multi-year seasonal climatology."
        )
    else:
        explanation = (
            "Recent same-station history supports a robust baseline and "
            "same 15-minute time-of-day comparison; this is not a multi-year "
            "seasonal climatology."
        )

    return {
        "station_id": station_id,
        "status": "ok",
        "baseline_quality": baseline_quality,
        "samples_used": sample_count,
        "time_of_day_samples": time_of_day_sample_count,
        "baseline": _baseline_metrics(usable_rows),
        "time_of_day_baseline": _baseline_metrics(time_of_day_rows),
        "explanation": explanation,
    }


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


@app.get("/station/{station_id}/health")
def station_health(station_id: str):
    known_station_ids = set(stations_df["station_id"].astype(str))
    if station_id not in known_station_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown station: {station_id}",
        )

    history_rows = get_station_feature_history_batch(
        [station_id],
        limit=672,
    )
    anomaly_rows = get_live_anomaly_history([station_id])
    return _calculate_station_health(
        station_id,
        history_rows,
        anomaly_rows,
    )


@app.get("/stations/health")
def stations_health():
    station_ids = stations_df["station_id"].astype(str).tolist()
    history_rows = get_station_feature_history_batch(
        station_ids,
        limit=672,
    )
    anomaly_rows = get_live_anomaly_history(station_ids)

    histories_by_station = {station_id: [] for station_id in station_ids}
    for row in history_rows:
        histories_by_station.setdefault(str(row["station_id"]), []).append(row)

    anomalies_by_station = {station_id: [] for station_id in station_ids}
    for row in anomaly_rows:
        anomalies_by_station.setdefault(str(row["station_id"]), []).append(row)

    latest_by_station = {}
    for station_id, rows in histories_by_station.items():
        if rows:
            latest_by_station[station_id] = max(
                rows,
                key=lambda row: _health_timestamp(row.get("timestamp"))
                or pd.Timestamp.min.tz_localize("Asia/Kolkata"),
            )

    contexts_by_timestamp = {}
    for station_id, latest in latest_by_station.items():
        timestamp = _health_timestamp(latest.get("timestamp"))
        if timestamp is None:
            continue
        contexts_by_timestamp.setdefault(timestamp, []).append({
            "station_id": station_id,
            "timestamp": timestamp,
            "temperature_c": latest.get("temperature_c"),
            "relative_humidity_pct": latest.get("relative_humidity_pct"),
            "pressure_hpa": latest.get("pressure_hpa"),
        })

    previous_contexts_by_timestamp = {}
    for rows in histories_by_station.values():
        for row in rows:
            timestamp = _health_timestamp(row.get("timestamp"))
            if timestamp is None:
                continue
            previous_contexts_by_timestamp.setdefault(timestamp, []).append({
                "station_id": row.get("station_id"),
                "timestamp": timestamp,
                "temperature_c": row.get("temperature_c"),
                "relative_humidity_pct": row.get("relative_humidity_pct"),
                "pressure_hpa": row.get("pressure_hpa"),
            })

    results = []
    for station_id in station_ids:
        latest = latest_by_station.get(station_id)
        timestamp = (
            _health_timestamp(latest.get("timestamp"))
            if latest is not None
            else None
        )
        results.append(
            _calculate_station_health(
                station_id,
                histories_by_station.get(station_id, []),
                anomalies_by_station.get(station_id, []),
                current_context=(
                    contexts_by_timestamp.get(timestamp)
                    if timestamp is not None
                    else []
                ),
                previous_context=(
                    previous_contexts_by_timestamp.get(
                        timestamp - pd.Timedelta(minutes=15)
                    )
                    if timestamp is not None
                    else []
                ),
            )
        )

    return {
        "stations": results,
        "station_count": len(results),
    }

def _maintenance_health_anchor(
    station_id,
    history_rows,
    anomaly_rows,
    target_timestamp,
    contexts_by_timestamp,
    previous_contexts_by_timestamp,
):
    target = _health_timestamp(target_timestamp)
    if target is None:
        return None

    eligible = []
    for row in history_rows or []:
        timestamp = _health_timestamp(row.get("timestamp"))
        if timestamp is not None and timestamp <= target:
            eligible.append(row)

    if not eligible:
        return None

    latest = max(
        eligible,
        key=lambda row: _health_timestamp(row.get("timestamp"))
        or pd.Timestamp.min.tz_localize("Asia/Kolkata"),
    )

    actual_timestamp = _health_timestamp(latest.get("timestamp"))
    if actual_timestamp is None:
        return None

    current_context = contexts_by_timestamp.get(actual_timestamp, [])

    previous_context = previous_contexts_by_timestamp.get(
        actual_timestamp - pd.Timedelta(minutes=15),
        [],
    )

    return _calculate_station_health(
        station_id,
        eligible,
        anomaly_rows,
        current_context=current_context,
        previous_context=previous_context,
        now=actual_timestamp,
    )

def _build_maintenance_risk_results():
    station_ids = stations_df["station_id"].astype(str).tolist()

    history_rows = get_station_feature_history_batch(
        station_ids,
        limit=672,
    )
    anomaly_rows = get_live_anomaly_history(station_ids)

    histories_by_station = {station_id: [] for station_id in station_ids}
    for row in history_rows:
        histories_by_station.setdefault(
            str(row["station_id"]),
            [],
        ).append(row)

    anomalies_by_station = {station_id: [] for station_id in station_ids}
    for row in anomaly_rows:
        anomalies_by_station.setdefault(
            str(row["station_id"]),
            [],
        ).append(row)

    # Build fleet-wide contexts for every timestamp already present
    # in the fetched seven-day history. No extra database queries
    # are needed for the sparse anchors.
    contexts_by_timestamp = {}
    previous_contexts_by_timestamp = {}

    for row in history_rows:
        timestamp = _health_timestamp(row.get("timestamp"))
        if timestamp is None:
            continue

        context_row = {
            "station_id": row.get("station_id"),
            "timestamp": timestamp,
            "temperature_c": row.get("temperature_c"),
            "relative_humidity_pct": row.get("relative_humidity_pct"),
            "pressure_hpa": row.get("pressure_hpa"),
        }

        contexts_by_timestamp.setdefault(
            timestamp,
            [],
        ).append(context_row)

        previous_contexts_by_timestamp.setdefault(
            timestamp,
            [],
        ).append(context_row)

    current_results = []

    for station_id in station_ids:
        rows = histories_by_station.get(station_id, [])
        anomalies = anomalies_by_station.get(station_id, [])

        if not rows:
            health = _calculate_station_health(
                station_id,
                [],
                anomalies,
            )
            current_results.append(
                risk_from_health(
                    health,
                    anomalies,
                    pd.Timestamp.now(tz="Asia/Kolkata"),
                )
                | {
                    "station_id": station_id,
                    "trajectory": {
                        "status": "unknown",
                        "direction": "unknown",
                        "delta_risk": None,
                        "slope_per_hour": None,
                        "reference_window": None,
                        "elevated_duration": None,
                        "recovery_detected": False,
                    },
                    "attention_horizon": None,
                    "data_sufficiency": health.get("data_sufficiency"),
                }
            )
            continue

        latest_timestamp = max(
            (
                _health_timestamp(row.get("timestamp"))
                for row in rows
                if _health_timestamp(row.get("timestamp")) is not None
            ),
            default=None,
        )

        if latest_timestamp is None:
            health = _calculate_station_health(
                station_id,
                [],
                anomalies,
            )
            current_results.append(
                risk_from_health(
                    health,
                    anomalies,
                    pd.Timestamp.now(tz="Asia/Kolkata"),
                )
                | {
                    "station_id": station_id,
                    "trajectory": {
                        "status": "unknown",
                        "direction": "unknown",
                        "delta_risk": None,
                        "slope_per_hour": None,
                        "reference_window": None,
                        "elevated_duration": None,
                        "recovery_detected": False,
                    },
                    "attention_horizon": None,
                    "data_sufficiency": health.get("data_sufficiency"),
                }
            )
            continue

        current_health = _calculate_station_health(
            station_id,
            rows,
            anomalies,
            current_context=contexts_by_timestamp.get(
                latest_timestamp,
                [],
            ),
            previous_context=previous_contexts_by_timestamp.get(
                latest_timestamp - pd.Timedelta(minutes=15),
                [],
            ),
            now=latest_timestamp,
        )

        current_risk = risk_from_health(
            current_health,
            anomalies,
            latest_timestamp,
        )

        anchors = {}

        for label, offset in (
            ("6h", pd.Timedelta(hours=6)),
            ("24h", pd.Timedelta(hours=24)),
            ("7d", pd.Timedelta(days=7)),
        ):
            anchor_health = _maintenance_health_anchor(
                station_id,
                rows,
                anomalies,
                latest_timestamp - offset,
                contexts_by_timestamp,
                previous_contexts_by_timestamp,
            )

            if anchor_health is not None:
                anchors[label] = risk_from_health(
                    anchor_health,
                    anomalies,
                    _health_timestamp(anchor_health.get("timestamp")),
                )
            else:
                anchors[label] = None

        result = attach_trajectory_and_horizon(
            current_risk,
            anchors,
        )

        result["station_id"] = station_id
        result["data_sufficiency"] = current_health.get(
            "data_sufficiency"
        )

        current_results.append(result)

    return rank_maintenance_results(current_results)

@app.get("/stations/maintenance-risk")
def stations_maintenance_risk():
    results = _build_maintenance_risk_results()

    ranked_count = sum(
        result.get("maintenance_risk") is not None
        and result.get("confidence") != "none"
        for result in results
    )

    insufficient_count = len(results) - ranked_count

    return {
        "stations": results,
        "station_count": len(results),
        "ranked_count": ranked_count,
        "insufficient_count": insufficient_count,
        "index_definition": "deterministic_maintenance_risk_v1",
    }

@app.get("/station/{station_id}/maintenance-risk")
def station_maintenance_risk(station_id: str):
    known_station_ids = set(
        stations_df["station_id"].astype(str)
    )

    if station_id not in known_station_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown station: {station_id}",
        )

    results = _build_maintenance_risk_results()

    for result in results:
        if str(result.get("station_id")) == station_id:
            return result

    raise HTTPException(
        status_code=404,
        detail=f"Maintenance-risk result unavailable for station: {station_id}",
    )

@app.get("/station/{station_id}/explain")
def explain_station_anomaly(
    station_id: str,
    top_k: int = 8,
):
    if station_id not in set(stations_df["station_id"].astype(str)):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown station: {station_id}",
        )

    if top_k < 1 or top_k > 15:
        raise HTTPException(
            status_code=422,
            detail="top_k must be between 1 and 15.",
        )

    latest_rows = get_latest_per_station()
    latest_by_station = {
        str(row.get("station_id")): row
        for row in latest_rows
    }
    latest = latest_by_station.get(station_id)

    if latest is None:
        raise HTTPException(
            status_code=422,
            detail="Insufficient current telemetry for this station.",
        )

    current_timestamp = _normalize_ingest_timestamp(
        str(latest.get("timestamp"))
    )
    history_rows = get_station_feature_history(
        station_id=station_id,
        before_timestamp=current_timestamp,
        limit=96,
    )
    if not history_rows:
        raise HTTPException(
            status_code=422,
            detail="Insufficient station history to build model features.",
        )

    reading = RawTelemetry(
        station_id=station_id,
        timestamp=current_timestamp.isoformat(),
        temperature_c=latest.get("temperature_c"),
        relative_humidity_pct=latest.get("relative_humidity_pct"),
        pressure_hpa=latest.get("pressure_hpa"),
    )
    spatial_context = pd.DataFrame([
        {
            "station_id": row.get("station_id"),
            "timestamp": row.get("timestamp"),
            "temperature_c": row.get("temperature_c"),
            "relative_humidity_pct": row.get(
                "relative_humidity_pct"
            ),
            "pressure_hpa": row.get("pressure_hpa"),
        }
        for row in latest_rows
    ])

    try:
        _, features, evidence = _build_live_prediction_context(
            reading,
            spatial_context=spatial_context,
        )
        row = _model_input_row(features)
        if not np.isfinite(row.to_numpy(dtype=float)).all():
            raise ValueError(
                "Model input contains non-finite values."
            )

        model_result = _run_real_models(
            features,
            evidence=evidence,
            station_id=station_id,
        )
        anomaly_probability = float(
            model_anomaly.predict_proba(row)[0][1]
        )
        top_features = _explain_anomaly_row(
            row,
            top_k=top_k,
        )

        return {
            "station_id": station_id,
            "timestamp": current_timestamp.isoformat(),
            "anomaly": bool(model_result["anomaly"]),
            "anomaly_probability": anomaly_probability,
            "feature_count": len(feature_cols),
            "model": "model_anomaly_detector.pkl",
            "algorithm": "RandomForestClassifier",
            "explained_class": 1,
            "explained_class_label": "anomaly",
            "top_features": top_features,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "SHAP explanation failed for station %s",
            station_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to generate anomaly explanation.",
        ) from exc


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