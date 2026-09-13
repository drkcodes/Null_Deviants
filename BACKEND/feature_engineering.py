from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import math
import pandas as pd


# ============================================================
# EXACT MODEL FEATURE CONTRACT
# ============================================================

FEATURE_COLS = [
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
# CONSTANTS
# ============================================================

MISSING_MODEL_VALUE = -999.0

EXPECTED_INTERVAL_SECONDS = 15 * 60

ROLLING_1H_ROWS = 4
ROLLING_6H_ROWS = 24

LAG_15MIN_ROWS = 1
LAG_1H_ROWS = 4
LAG_3H_ROWS = 12
LAG_24H_ROWS = 96

# Magnus formula constants.
MAGNUS_A = 17.62
MAGNUS_B = 243.12


# ============================================================
# STATION METADATA
# ============================================================

DEFAULT_STATIONS_FILE = Path(__file__).resolve().parent / "stations.csv"


@dataclass
class StationContext:
    """
    Static metadata for a weather station.
    """

    station_id: str
    nearest_station_id: Optional[str] = None


# ============================================================
# NUMERIC HELPERS
# ============================================================

def _to_float(
    value,
    default: float = float("nan"),
) -> float:

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):

        return default


def _safe_difference(
    current: float,
    previous: float,
) -> float:

    if (
        pd.isna(current)
        or pd.isna(previous)
        or previous == MISSING_MODEL_VALUE
    ):
        return MISSING_MODEL_VALUE

    return float(current - previous)


def _safe_rate_of_change(
    current: float,
    previous: float,
) -> float:

    if (
        pd.isna(current)
        or pd.isna(previous)
        or previous == MISSING_MODEL_VALUE
    ):
        return MISSING_MODEL_VALUE

    return float(current - previous)


# ============================================================
# TIMESTAMP
# ============================================================

def _parse_timestamp(value) -> pd.Timestamp:

    timestamp = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(timestamp):

        raise ValueError(
            f"Invalid timestamp: {value}"
        )

    return timestamp


# ============================================================
# MISSING VALUE FLAGS
# ============================================================

def _missing_flag(value) -> float:

    return float(
        value is None
        or pd.isna(value)
    )


# ============================================================
# DEW POINT
# ============================================================

def _dew_point(
    temperature_c: float,
    relative_humidity_pct: float,
) -> float:

    if (
        pd.isna(temperature_c)
        or pd.isna(relative_humidity_pct)
    ):
        return float("nan")

    if relative_humidity_pct <= 0:
        return float("nan")

    if relative_humidity_pct > 100:
        relative_humidity_pct = 100.0

    gamma = (
        math.log(relative_humidity_pct / 100.0)
        + (
            MAGNUS_A * temperature_c
            / (MAGNUS_B + temperature_c)
        )
    )

    return (
        MAGNUS_B * gamma
        / (MAGNUS_A - gamma)
    )


# ============================================================
# HISTORY NORMALIZATION
# ============================================================

def _prepare_history(
    history: Optional[pd.DataFrame],
) -> pd.DataFrame:

    if history is None or history.empty:

        return pd.DataFrame(
            columns=[
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        )

    required = [
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]

    missing = [
        column
        for column in required
        if column not in history.columns
    ]

    if missing:

        raise ValueError(
            "History is missing required columns: "
            + ", ".join(missing)
        )

    result = history[
        required
    ].copy()

    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        errors="coerce",
    )

    result = result.dropna(
        subset=["timestamp"]
    )

    result = result.sort_values(
        "timestamp"
    )

    result = result.reset_index(
        drop=True
    )

    for column in [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]:

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    return result


# ============================================================
# LAG HELPERS
# ============================================================

def _lag(
    series: pd.Series,
    rows: int,
) -> float:

    if len(series) <= rows:
        return MISSING_MODEL_VALUE

    value = series.iloc[-rows - 1]

    if pd.isna(value):
        return MISSING_MODEL_VALUE

    return float(value)


# ============================================================
# ROLLING STATISTICS
# ============================================================

def _rolling_mean(
    series: pd.Series,
    window: int,
) -> float:

    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    if values.empty:
        return MISSING_MODEL_VALUE

    result = values.tail(window).mean()

    if pd.isna(result):
        return MISSING_MODEL_VALUE

    return float(result)


def _rolling_std(
    series: pd.Series,
    window: int,
) -> float:

    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    if values.empty:
        return MISSING_MODEL_VALUE

    result = values.tail(window).std(
        ddof=1
    )

    if pd.isna(result):
        return MISSING_MODEL_VALUE

    return float(result)


def _zscore(
    current: float,
    series: pd.Series,
    window: int,
) -> float:

    if pd.isna(current):
        return MISSING_MODEL_VALUE

    values = pd.to_numeric(
        series.tail(window),
        errors="coerce",
    ).dropna()

    if len(values) < 2:
        return MISSING_MODEL_VALUE

    mean = values.mean()
    std = values.std(ddof=1)

    if pd.isna(std) or std == 0:
        return 0.0

    return float(
        (current - mean) / std
    )


# ============================================================
# STUCK VALUE COUNT
# ============================================================

def _stuck_count(values: pd.Series) -> float:
    """
    Return the number of consecutive identical previous/current readings.

    Semantics:
    - First valid reading -> 0
    - A changed reading -> 0
    - Repeated identical readings -> number of consecutive repeats
    - Missing value -> 0
    """
    if values is None or len(values) == 0:
        return 0.0

    series = pd.to_numeric(values, errors="coerce")

    if pd.isna(series.iloc[-1]):
        return 0.0

    current = float(series.iloc[-1])
    count = 0

    for i in range(len(series) - 2, -1, -1):
        previous = series.iloc[i]

        if pd.isna(previous):
            break

        if float(previous) == current:
            count += 1
        else:
            break

    return float(count)


# ============================================================
# SPATIAL HELPERS
# ============================================================

def _spatial_context(
    station_id: str,
    current_timestamp: pd.Timestamp,
    current_temperature: float,
    current_humidity: float,
    current_pressure: float,
    all_station_history: Optional[pd.DataFrame],
) -> dict:

    result = {
        "spatial_temp_diff": MISSING_MODEL_VALUE,
        "spatial_humidity_diff": MISSING_MODEL_VALUE,
        "spatial_pressure_diff": MISSING_MODEL_VALUE,
        "regional_temp_zscore": MISSING_MODEL_VALUE,
    }

    if (
        all_station_history is None
        or all_station_history.empty
    ):
        return result

    required = {
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    }

    if not required.issubset(
        all_station_history.columns
    ):
        return result

    data = all_station_history.copy()

    data["timestamp"] = pd.to_datetime(
        data["timestamp"],
        errors="coerce",
    )

    data = data.dropna(
        subset=["timestamp"]
    )

    # Use readings at the same timestamp.
    same_time = data[
        data["timestamp"]
        == current_timestamp
    ].copy()

    if same_time.empty:
        return result

    # --------------------------------------------------------
    # Find nearest station from metadata.
    # --------------------------------------------------------

    station_file = DEFAULT_STATIONS_FILE

    nearest_station_id = None

    if station_file.exists():

        try:

            stations = pd.read_csv(
                station_file
            )

            row = stations[
                stations["station_id"].astype(str)
                == str(station_id)
            ]

            if not row.empty:

                nearest_station_id = str(
                    row.iloc[0][
                        "nearest_station_id"
                    ]
                )

        except Exception:
            nearest_station_id = None

    # --------------------------------------------------------
    # Nearest-station comparison.
    # --------------------------------------------------------

    if nearest_station_id:

        neighbour = same_time[
            same_time["station_id"].astype(str)
            == nearest_station_id
        ]

        if not neighbour.empty:

            neighbour_row = neighbour.iloc[0]

            neighbour_temperature = _to_float(
                neighbour_row["temperature_c"]
            )

            neighbour_humidity = _to_float(
                neighbour_row[
                    "relative_humidity_pct"
                ]
            )

            neighbour_pressure = _to_float(
                neighbour_row["pressure_hpa"]
            )

            if not (
                pd.isna(current_temperature)
                or pd.isna(neighbour_temperature)
            ):

                result[
                    "spatial_temp_diff"
                ] = float(
                    current_temperature
                    - neighbour_temperature
                )

            if not (
                pd.isna(current_humidity)
                or pd.isna(neighbour_humidity)
            ):

                result[
                    "spatial_humidity_diff"
                ] = float(
                    current_humidity
                    - neighbour_humidity
                )

            if not (
                pd.isna(current_pressure)
                or pd.isna(neighbour_pressure)
            ):

                result[
                    "spatial_pressure_diff"
                ] = float(
                    current_pressure
                    - neighbour_pressure
                )

    # --------------------------------------------------------
    # Regional temperature z-score.
    #
    # Region is obtained from stations.csv.
    # --------------------------------------------------------

    if station_file.exists():

        try:

            stations = pd.read_csv(
                station_file
            )

            stations["station_id"] = (
                stations["station_id"]
                .astype(str)
            )

            station_row = stations[
                stations["station_id"]
                == str(station_id)
            ]

            if not station_row.empty:

                region = str(
                    station_row.iloc[0][
                        "region"
                    ]
                )

                region_station_ids = set(
                    stations[
                        stations["region"]
                        == region
                    ]["station_id"]
                    .astype(str)
                )

                regional = same_time[
                    same_time["station_id"]
                    .astype(str)
                    .isin(region_station_ids)
                ]

                temperatures = pd.to_numeric(
                    regional["temperature_c"],
                    errors="coerce",
                ).dropna()

                if (
                    len(temperatures) >= 2
                    and not pd.isna(
                        current_temperature
                    )
                ):

                    mean = temperatures.mean()

                    std = temperatures.std(
                        ddof=1
                    )

                    if (
                        not pd.isna(std)
                        and std > 0
                    ):

                        result[
                            "regional_temp_zscore"
                        ] = float(
                            (
                                current_temperature
                                - mean
                            ) / std
                        )

        except Exception:
            pass

    return result


# ============================================================
# FEATURE ENGINE
# ============================================================

def build_features(
    station_id: str,
    timestamp,
    temperature_c,
    relative_humidity_pct,
    pressure_hpa,
    history: Optional[pd.DataFrame] = None,
    all_station_history: Optional[pd.DataFrame] = None,
) -> dict:

    """
    Convert one raw AWS observation into the exact
    50-feature vector expected by the trained models.

    Parameters
    ----------
    station_id:
        AWS station identifier.

    timestamp:
        Observation timestamp.

    temperature_c:
        Raw observed temperature.

    relative_humidity_pct:
        Raw observed relative humidity.

    pressure_hpa:
        Raw observed atmospheric pressure.

    history:
        Previous observations for THIS station only.

    all_station_history:
        Observations from all stations used for spatial
        consistency calculations.

    Returns
    -------
    dict
        Exactly 50 model features.
    """

    current_timestamp = _parse_timestamp(
        timestamp
    )

    current_temperature = _to_float(
        temperature_c
    )

    current_humidity = _to_float(
        relative_humidity_pct
    )

    current_pressure = _to_float(
        pressure_hpa
    )

    station_history = _prepare_history(
        history
    )

    # --------------------------------------------------------
    # Ensure current observation is represented at the end
    # of the working sequence.
    # --------------------------------------------------------

    current_row = pd.DataFrame(
        [
            {
                "timestamp": current_timestamp,
                "temperature_c": current_temperature,
                "relative_humidity_pct": current_humidity,
                "pressure_hpa": current_pressure,
            }
        ]
    )

    sequence = pd.concat(
        [
            station_history,
            current_row,
        ],
        ignore_index=True,
    )

    sequence = sequence.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Locate the actual current observation.
    # --------------------------------------------------------

    current_index = (
        sequence["timestamp"]
        == current_timestamp
    )

    if not current_index.any():

        raise RuntimeError(
            "Current observation could not be "
            "located in the feature-engineering sequence."
        )

    current_position = (
        sequence.index[current_index][-1]
    )

    temperature_series = sequence[
        "temperature_c"
    ].iloc[:current_position + 1]

    humidity_series = sequence[
        "relative_humidity_pct"
    ].iloc[:current_position + 1]

    pressure_series = sequence[
        "pressure_hpa"
    ].iloc[:current_position + 1]

    # ========================================================
    # RAW VALUES
    # ========================================================

    features = {

        "temperature_c":
            current_temperature,

        "relative_humidity_pct":
            current_humidity,

        "pressure_hpa":
            current_pressure,
    }

    # ========================================================
    # TEMPERATURE
    # ========================================================

    temperature_lag_15 = _lag(
        temperature_series,
        LAG_15MIN_ROWS,
    )

    temperature_lag_1h = _lag(
        temperature_series,
        LAG_1H_ROWS,
    )

    temperature_lag_3h = _lag(
        temperature_series,
        LAG_3H_ROWS,
    )

    features[
        "temperature_lag_15min"
    ] = temperature_lag_15

    features[
        "temperature_lag_1h"
    ] = temperature_lag_1h

    features[
        "temperature_lag_3h"
    ] = temperature_lag_3h

    features[
        "temperature_roc_15min"
    ] = _safe_rate_of_change(
        current_temperature,
        temperature_lag_15,
    )

    features[
        "temperature_roc_1h"
    ] = _safe_rate_of_change(
        current_temperature,
        temperature_lag_1h,
    )

    features[
        "temperature_rollmean_1h"
    ] = _rolling_mean(
        temperature_series,
        ROLLING_1H_ROWS,
    )

    features[
        "temperature_rollstd_1h"
    ] = _rolling_std(
        temperature_series,
        ROLLING_1H_ROWS,
    )

    features[
        "temperature_rollmean_6h"
    ] = _rolling_mean(
        temperature_series,
        ROLLING_6H_ROWS,
    )

    features[
        "temperature_rollstd_6h"
    ] = _rolling_std(
        temperature_series,
        ROLLING_6H_ROWS,
    )

    features[
        "temperature_zscore_6h"
    ] = _zscore(
        current_temperature,
        temperature_series,
        ROLLING_6H_ROWS,
    )

    # ========================================================
    # HUMIDITY
    # ========================================================

    humidity_lag_15 = _lag(
        humidity_series,
        LAG_15MIN_ROWS,
    )

    humidity_lag_1h = _lag(
        humidity_series,
        LAG_1H_ROWS,
    )

    humidity_lag_3h = _lag(
        humidity_series,
        LAG_3H_ROWS,
    )

    features[
        "humidity_lag_15min"
    ] = humidity_lag_15

    features[
        "humidity_lag_1h"
    ] = humidity_lag_1h

    features[
        "humidity_lag_3h"
    ] = humidity_lag_3h

    features[
        "humidity_roc_15min"
    ] = _safe_rate_of_change(
        current_humidity,
        humidity_lag_15,
    )

    features[
        "humidity_roc_1h"
    ] = _safe_rate_of_change(
        current_humidity,
        humidity_lag_1h,
    )

    features[
        "humidity_rollmean_1h"
    ] = _rolling_mean(
        humidity_series,
        ROLLING_1H_ROWS,
    )

    features[
        "humidity_rollstd_1h"
    ] = _rolling_std(
        humidity_series,
        ROLLING_1H_ROWS,
    )

    features[
        "humidity_rollmean_6h"
    ] = _rolling_mean(
        humidity_series,
        ROLLING_6H_ROWS,
    )

    features[
        "humidity_rollstd_6h"
    ] = _rolling_std(
        humidity_series,
        ROLLING_6H_ROWS,
    )

    features[
        "humidity_zscore_6h"
    ] = _zscore(
        current_humidity,
        humidity_series,
        ROLLING_6H_ROWS,
    )

    # ========================================================
    # PRESSURE
    # ========================================================

    pressure_lag_15 = _lag(
        pressure_series,
        LAG_15MIN_ROWS,
    )

    pressure_lag_1h = _lag(
        pressure_series,
        LAG_1H_ROWS,
    )

    pressure_lag_3h = _lag(
        pressure_series,
        LAG_3H_ROWS,
    )

    features[
        "pressure_lag_15min"
    ] = pressure_lag_15

    features[
        "pressure_lag_1h"
    ] = pressure_lag_1h

    features[
        "pressure_lag_3h"
    ] = pressure_lag_3h

    features[
        "pressure_roc_15min"
    ] = _safe_rate_of_change(
        current_pressure,
        pressure_lag_15,
    )

    features[
        "pressure_roc_1h"
    ] = _safe_rate_of_change(
        current_pressure,
        pressure_lag_1h,
    )

    features[
        "pressure_rollmean_1h"
    ] = _rolling_mean(
        pressure_series,
        ROLLING_1H_ROWS,
    )

    features[
        "pressure_rollstd_1h"
    ] = _rolling_std(
        pressure_series,
        ROLLING_1H_ROWS,
    )

    features[
        "pressure_rollmean_6h"
    ] = _rolling_mean(
        pressure_series,
        ROLLING_6H_ROWS,
    )

    features[
        "pressure_rollstd_6h"
    ] = _rolling_std(
        pressure_series,
        ROLLING_6H_ROWS,
    )

    features[
        "pressure_zscore_6h"
    ] = _zscore(
        current_pressure,
        pressure_series,
        ROLLING_6H_ROWS,
    )

    # ========================================================
    # STUCK VALUE DETECTION
    # ========================================================

    features[
        "temperature_stuck_count"
    ] = _stuck_count(
        temperature_series
    )

    features[
        "humidity_stuck_count"
    ] = _stuck_count(
        humidity_series
    )

    features[
        "pressure_stuck_count"
    ] = _stuck_count(
        pressure_series
    )

    # ========================================================
    # MULTIVARIATE PHYSICAL CONSISTENCY
    # ========================================================

    dew_point = _dew_point(
        current_temperature,
        current_humidity,
    )

    if pd.isna(dew_point):

        dew_point_deficit = (
            MISSING_MODEL_VALUE
        )

        physically_implausible = 0.0

    else:

        dew_point_deficit = (
            current_temperature
            - dew_point
        )

        physically_implausible = float(
            dew_point_deficit < -0.5
        )

    features[
        "dew_point_deficit_c"
    ] = dew_point_deficit

    features[
        "physically_implausible_flag"
    ] = physically_implausible

    # ========================================================
    # SPATIAL CONSISTENCY
    # ========================================================

    spatial = _spatial_context(
        station_id=station_id,
        current_timestamp=current_timestamp,
        current_temperature=current_temperature,
        current_humidity=current_humidity,
        current_pressure=current_pressure,
        all_station_history=all_station_history,
    )

    features.update(
        spatial
    )

    # ========================================================
    # MISSING DATA FLAGS
    # ========================================================

    features[
        "is_missing_temperature"
    ] = _missing_flag(
        temperature_c
    )

    features[
        "is_missing_humidity"
    ] = _missing_flag(
        relative_humidity_pct
    )

    features[
        "is_missing_pressure"
    ] = _missing_flag(
        pressure_hpa
    )

    # ========================================================
    # TIMESTAMP QUALITY
    # ========================================================

    timestamp_gap_seconds = (
        MISSING_MODEL_VALUE
    )

    timestamp_gap_flag = 1.0

    if current_position > 0:

        previous_timestamp = (
            sequence.iloc[
                current_position - 1
            ]["timestamp"]
        )

        gap = (
            current_timestamp
            - previous_timestamp
        ).total_seconds()

        timestamp_gap_seconds = float(
            gap
        )

        timestamp_gap_flag = float(
            gap != EXPECTED_INTERVAL_SECONDS
        )

    features[
        "timestamp_gap_seconds"
    ] = timestamp_gap_seconds

    features[
        "timestamp_gap_flag"
    ] = timestamp_gap_flag

    # ========================================================
    # 24-HOUR DEVIATION
    # ========================================================

    temperature_lag_24 = _lag(
        temperature_series,
        LAG_24H_ROWS,
    )

    humidity_lag_24 = _lag(
        humidity_series,
        LAG_24H_ROWS,
    )

    pressure_lag_24 = _lag(
        pressure_series,
        LAG_24H_ROWS,
    )

    features[
        "temperature_dev_24h"
    ] = _safe_difference(
        current_temperature,
        temperature_lag_24,
    )

    features[
        "humidity_dev_24h"
    ] = _safe_difference(
        current_humidity,
        humidity_lag_24,
    )

    features[
        "pressure_dev_24h"
    ] = _safe_difference(
        current_pressure,
        pressure_lag_24,
    )

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    missing_features = [
        column
        for column in FEATURE_COLS
        if column not in features
    ]

    if missing_features:

        raise RuntimeError(
            "Feature engine failed to produce: "
            + ", ".join(missing_features)
        )

    extra_features = [
        column
        for column in features
        if column not in FEATURE_COLS
    ]

    if extra_features:

        raise RuntimeError(
            "Feature engine produced unexpected "
            "features: "
            + ", ".join(extra_features)
        )

    # Preserve the exact model column order.
    features = {
        column: features[column]
        for column in FEATURE_COLS
    }

    return features


# ============================================================
# MODEL-READY DATAFRAME
# ============================================================

def build_model_row(
    features: dict,
) -> pd.DataFrame:

    """
    Convert the 50-feature dictionary into the exact
    DataFrame structure expected by the trained model.
    """

    missing = [
        column
        for column in FEATURE_COLS
        if column not in features
    ]

    if missing:

        raise ValueError(
            "Missing model features: "
            + ", ".join(missing)
        )

    row = pd.DataFrame(
        [
            {
                column: features[column]
                for column in FEATURE_COLS
            }
        ]
    )

    return row[
        FEATURE_COLS
    ].fillna(
        MISSING_MODEL_VALUE
    )