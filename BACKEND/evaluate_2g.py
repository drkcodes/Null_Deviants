import time
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# SKYGUARD AI — 2G EVALUATION HARNESS
# ============================================================
#
# Purpose:
#   Controlled validation of the raw-telemetry /ingest pipeline.
#
# Important:
#   This is an EVALUATION TOOL.
#   It does NOT modify:
#       - simulate.py
#       - main.py
#       - feature_engineering.py
#       - trained models
#
# Every test sends RAW T / RH / Pressure to /ingest.
#
# ============================================================


API_URL = "http://127.0.0.1:8000/ingest"
HEALTH_URL = "http://127.0.0.1:8000/"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

REQUEST_DELAY = 0.25

# We use the end of the seeded historical period.
#
# Historical DB:
#   2025-12-24 -> 2025-12-30
#
# Evaluation stream:
#   2025-12-31
#
# Therefore the feature engine has preceding historical context.

EVAL_START = pd.Timestamp("2025-12-31 00:00:00")

STATIONS = [
    f"AWS_AP{i:02d}"
    for i in range(1, 21)
]


# ============================================================
# HELPERS
# ============================================================

def check_backend():
    print("\nChecking backend...")

    response = requests.get(
        HEALTH_URL,
        timeout=5,
    )

    response.raise_for_status()

    print("Backend: ONLINE")


def load_dataset():
    print("\nLoading dataset...")

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{DATASET_PATH}"
        )

    df = pd.read_csv(DATASET_PATH)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = df.sort_values(
        [
            "timestamp",
            "station_id",
        ]
    ).reset_index(drop=True)

    print(
        f"Loaded {len(df):,} observations"
    )

    print(
        f"Stations: "
        f"{df['station_id'].nunique()}"
    )

    return df


def get_baseline(df, timestamp):
    rows = df[
        df["timestamp"] == timestamp
    ].copy()

    rows = rows[
        rows["station_id"].isin(STATIONS)
    ]

    if rows.empty:
        raise RuntimeError(
            f"No dataset observations at {timestamp}"
        )

    return rows


def send_reading(
    station_id,
    timestamp,
    temperature_c,
    relative_humidity_pct,
    pressure_hpa,
):
    payload = {
        "station_id": station_id,
        "timestamp": timestamp.isoformat(),
        "temperature_c": (
            None
            if pd.isna(temperature_c)
            else float(temperature_c)
        ),
        "relative_humidity_pct": (
            None
            if pd.isna(relative_humidity_pct)
            else float(relative_humidity_pct)
        ),
        "pressure_hpa": (
            None
            if pd.isna(pressure_hpa)
            else float(pressure_hpa)
        ),
    }

    response = requests.post(
        API_URL,
        json=payload,
        timeout=5,
    )

    response.raise_for_status()

    return response.json()


def print_result(
    station_id,
    result,
    expected,
):
    anomaly = result.get(
        "anomaly"
    )

    classification = result.get(
        "weather_or_sensor",
        "none",
    )

    confidence = result.get(
        "confidence"
    )

    score = result.get(
        "anomaly_score"
    )

    print(
        f"{station_id:8} | "
        f"expected={expected:7} | "
        f"anomaly={str(anomaly):5} | "
        f"class={classification:7} | "
        f"score={score} | "
        f"confidence={confidence}"
    )


# ============================================================
# 2G.1
# NORMAL BASELINE
# ============================================================

def test_normal(df):
    print("\n" + "=" * 70)
    print("2G.1 — NORMAL BASELINE")
    print("=" * 70)

    rows = get_baseline(
        df,
        EVAL_START,
    )

    # Use one station for the clean baseline test.
    row = rows[
        rows["station_id"] == "AWS_AP08"
    ].iloc[0]

    result = send_reading(
        station_id="AWS_AP08",
        timestamp=EVAL_START,
        temperature_c=row["temperature_c"],
        relative_humidity_pct=row[
            "relative_humidity_pct"
        ],
        pressure_hpa=row["pressure_hpa"],
    )

    print_result(
        "AWS_AP08",
        result,
        "normal",
    )

    passed = (
        result.get("anomaly") is False
    )

    print(
        "\n2G.1:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# 2G.2
# REGIONAL WEATHER EVENT
# ============================================================

def test_regional_weather(df):
    print("\n" + "=" * 70)
    print("2G.2 — REGIONAL WEATHER EVENT")
    print("=" * 70)

    rows = get_baseline(
        df,
        EVAL_START + pd.Timedelta(minutes=15),
    )

    timestamp = (
        EVAL_START
        + pd.Timedelta(minutes=15)
    )

    results = []

    print(
        "\nInjecting coherent regional heatwave:"
    )
    print(
        "  Temperature +6°C"
    )
    print(
        "  RH -10 percentage points"
    )
    print(
        "  Pressure -5 hPa"
    )

    for _, row in rows.iterrows():

        result = send_reading(
            station_id=row["station_id"],
            timestamp=timestamp,
            temperature_c=(
                row["temperature_c"] + 6.0
            ),
            relative_humidity_pct=max(
                5.0,
                row["relative_humidity_pct"]
                - 10.0,
            ),
            pressure_hpa=(
                row["pressure_hpa"] - 5.0
            ),
        )

        results.append(result)

        print_result(
            row["station_id"],
            result,
            "weather",
        )

        time.sleep(
            REQUEST_DELAY
        )

    weather_count = sum(
        1
        for result in results
        if result.get("weather_or_sensor")
        == "weather"
    )

    anomaly_count = sum(
        1
        for result in results
        if result.get("anomaly")
    )

    print(
        f"\nAnomalies detected: "
        f"{anomaly_count}/{len(results)}"
    )

    print(
        f"Weather classifications: "
        f"{weather_count}/{len(results)}"
    )

    passed = (
        anomaly_count > 0
        and weather_count > 0
    )

    print(
        "\n2G.2:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# 2G.3
# SENSOR SPIKE
# ============================================================

def test_spike(df):
    print("\n" + "=" * 70)
    print("2G.3 — SENSOR SPIKE")
    print("=" * 70)

    timestamp = (
        EVAL_START
        + pd.Timedelta(minutes=30)
    )

    rows = get_baseline(
        df,
        timestamp,
    )

    target = rows[
        rows["station_id"] == "AWS_AP08"
    ].iloc[0]

    # Other stations remain normal.
    # AWS_AP08 receives a large isolated
    # temperature spike.

    for _, row in rows.iterrows():

        if row["station_id"] == "AWS_AP08":

            temperature = (
                row["temperature_c"]
                + 15.0
            )

            expected = "sensor"

        else:

            temperature = row[
                "temperature_c"
            ]

            expected = "normal"

        result = send_reading(
            station_id=row["station_id"],
            timestamp=timestamp,
            temperature_c=temperature,
            relative_humidity_pct=row[
                "relative_humidity_pct"
            ],
            pressure_hpa=row[
                "pressure_hpa"
            ],
        )

        if row["station_id"] == "AWS_AP08":

            print_result(
                row["station_id"],
                result,
                expected,
            )

            target_result = result

        time.sleep(
            REQUEST_DELAY
        )

    passed = (
        target_result.get("anomaly")
        is True
        and target_result.get(
            "weather_or_sensor"
        )
        == "sensor"
    )

    print(
        "\n2G.3:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# 2G.4
# SENSOR DRIFT
# ============================================================

def test_drift(df):
    print("\n" + "=" * 70)
    print("2G.4 — SENSOR DRIFT")
    print("=" * 70)

    base_time = (
        EVAL_START
        + pd.Timedelta(hours=1)
    )

    rows = get_baseline(
        df,
        base_time,
    )

    target = rows[
        rows["station_id"] == "AWS_AP08"
    ].iloc[0]

    target_result = None

    print(
        "\nApplying gradual temperature drift "
        "to AWS_AP08:"
    )

    print(
        "  +1°C, +2°C, +3°C, +4°C, +5°C"
    )

    for step in range(1, 6):

        timestamp = (
            base_time
            + pd.Timedelta(
                minutes=15 * (step - 1)
            )
        )

        temperature = (
            target["temperature_c"]
            + float(step)
        )

        result = send_reading(
            station_id="AWS_AP08",
            timestamp=timestamp,
            temperature_c=temperature,
            relative_humidity_pct=target[
                "relative_humidity_pct"
            ],
            pressure_hpa=target[
                "pressure_hpa"
            ],
        )

        target_result = result

        print_result(
            "AWS_AP08",
            result,
            "sensor",
        )

        time.sleep(
            REQUEST_DELAY
        )

    passed = (
        target_result is not None
        and target_result.get("anomaly")
        is True
        and target_result.get(
            "weather_or_sensor"
        )
        == "sensor"
    )

    print(
        "\n2G.4:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# 2G.5
# FROZEN SENSOR
# ============================================================

def test_frozen(df):
    print("\n" + "=" * 70)
    print("2G.5 — FROZEN SENSOR")
    print("=" * 70)

    base_time = (
        EVAL_START
        + pd.Timedelta(hours=2)
    )

    rows = get_baseline(
        df,
        base_time,
    )

    target = rows[
        rows["station_id"] == "AWS_AP08"
    ].iloc[0]

    frozen_t = target[
        "temperature_c"
    ]

    frozen_rh = target[
        "relative_humidity_pct"
    ]

    frozen_p = target[
        "pressure_hpa"
    ]

    target_result = None

    print(
        "\nRepeating identical telemetry "
        "for AWS_AP08."
    )

    for step in range(8):

        timestamp = (
            base_time
            + pd.Timedelta(
                minutes=15 * step
            )
        )

        result = send_reading(
            station_id="AWS_AP08",
            timestamp=timestamp,
            temperature_c=frozen_t,
            relative_humidity_pct=frozen_rh,
            pressure_hpa=frozen_p,
        )

        target_result = result

        print_result(
            "AWS_AP08",
            result,
            "sensor",
        )

        time.sleep(
            REQUEST_DELAY
        )

    passed = (
        target_result is not None
        and target_result.get("anomaly")
        is True
        and target_result.get(
            "weather_or_sensor"
        )
        == "sensor"
    )

    print(
        "\n2G.5:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# 2G.6
# MISSING TELEMETRY
# ============================================================

def test_missing(df):
    print("\n" + "=" * 70)
    print("2G.6 — MISSING TELEMETRY")
    print("=" * 70)

    timestamp = (
        EVAL_START
        + pd.Timedelta(hours=3)
    )

    rows = get_baseline(
        df,
        timestamp,
    )

    target = rows[
        rows["station_id"] == "AWS_AP08"
    ].iloc[0]

    # Send a complete reading immediately before
    # the missing observation so the timestamp sequence
    # remains meaningful.

    normal_time = timestamp - pd.Timedelta(
        minutes=15
    )

    send_reading(
        station_id="AWS_AP08",
        timestamp=normal_time,
        temperature_c=target[
            "temperature_c"
        ],
        relative_humidity_pct=target[
            "relative_humidity_pct"
        ],
        pressure_hpa=target[
            "pressure_hpa"
        ],
    )

    # All three measurements missing.

    result = send_reading(
        station_id="AWS_AP08",
        timestamp=timestamp,
        temperature_c=None,
        relative_humidity_pct=None,
        pressure_hpa=None,
    )

    print_result(
        "AWS_AP08",
        result,
        "missing",
    )

    print(
        "\nRaw missing telemetry was accepted "
        "by /ingest."
    )

    print(
        "features_computed_count:",
        result.get(
            "features_computed_count"
        ),
    )

    # Missing-data handling is considered a
    # pipeline/data-quality test rather than
    # requiring Stage 1 to classify it as a
    # sensor anomaly.

    passed = (
        result.get(
            "features_computed_count"
        )
        == 50
    )

    print(
        "\n2G.6:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# 2G.7
# WEATHER VS SENSOR DISCRIMINATION
# ============================================================

def test_discrimination(df):
    print("\n" + "=" * 70)
    print("2G.7 — WEATHER VS SENSOR DISCRIMINATION")
    print("=" * 70)

    weather_time = (
        EVAL_START
        + pd.Timedelta(hours=4)
    )

    sensor_time = (
        EVAL_START
        + pd.Timedelta(hours=5)
    )

    weather_rows = get_baseline(
        df,
        weather_time,
    )

    sensor_rows = get_baseline(
        df,
        sensor_time,
    )

    # --------------------------------------------------------
    # WEATHER:
    # coherent change across stations
    # --------------------------------------------------------

    weather_results = []

    for _, row in weather_rows.iterrows():

        result = send_reading(
            station_id=row["station_id"],
            timestamp=weather_time,
            temperature_c=(
                row["temperature_c"] + 7.0
            ),
            relative_humidity_pct=max(
                5.0,
                row["relative_humidity_pct"]
                - 12.0,
            ),
            pressure_hpa=(
                row["pressure_hpa"] - 6.0
            ),
        )

        weather_results.append(
            result
        )

        time.sleep(
            REQUEST_DELAY
        )

    weather_predictions = [
        result.get("weather_or_sensor")
        for result in weather_results
        if result.get("anomaly")
    ]

    # --------------------------------------------------------
    # SENSOR:
    # isolated station change
    # --------------------------------------------------------

    sensor_target = None

    for _, row in sensor_rows.iterrows():

        if row["station_id"] == "AWS_AP08":

            result = send_reading(
                station_id="AWS_AP08",
                timestamp=sensor_time,
                temperature_c=(
                    row["temperature_c"]
                    + 18.0
                ),
                relative_humidity_pct=row[
                    "relative_humidity_pct"
                ],
                pressure_hpa=row[
                    "pressure_hpa"
                ],
            )

            sensor_target = result

        else:

            send_reading(
                station_id=row["station_id"],
                timestamp=sensor_time,
                temperature_c=row[
                    "temperature_c"
                ],
                relative_humidity_pct=row[
                    "relative_humidity_pct"
                ],
                pressure_hpa=row[
                    "pressure_hpa"
                ],
            )

        time.sleep(
            REQUEST_DELAY
        )

    weather_detected = (
        "weather"
        in weather_predictions
    )

    sensor_detected = (
        sensor_target is not None
        and sensor_target.get("anomaly")
        is True
        and sensor_target.get(
            "weather_or_sensor"
        )
        == "sensor"
    )

    print(
        "\nWeather event classifications:",
        weather_predictions,
    )

    print(
        "\nSensor event:"
    )

    if sensor_target is not None:

        print_result(
            "AWS_AP08",
            sensor_target,
            "sensor",
        )

    passed = (
        weather_detected
        and sensor_detected
    )

    print(
        "\n2G.7:",
        "PASS" if passed else "FAIL",
    )

    return passed


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SKYGUARD AI — 2G EVALUATION")
    print("=" * 70)

    print(
        "\nDataset:"
        f"\n  {DATASET_PATH}"
    )

    print(
        "\nEvaluation stream:"
        f"\n  {EVAL_START}"
    )

    print(
        "\nAll scenarios use raw telemetry -> /ingest."
    )

    check_backend()

    df = load_dataset()

    results = {}

    # --------------------------------------------------------
    # Run tests
    # --------------------------------------------------------

    results["2G.1 Normal"] = test_normal(
        df
    )

    results["2G.2 Weather"] = test_regional_weather(
        df
    )

    results["2G.3 Spike"] = test_spike(
        df
    )

    results["2G.4 Drift"] = test_drift(
        df
    )

    results["2G.5 Frozen"] = test_frozen(
        df
    )

    results["2G.6 Missing"] = test_missing(
        df
    )

    results["2G.7 Discrimination"] = test_discrimination(
        df
    )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("2G FINAL RESULTS")
    print("=" * 70)

    passed_count = 0

    for name, passed in results.items():

        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{name:30} {status}"
        )

        if passed:
            passed_count += 1

    print(
        "\nPassed:",
        f"{passed_count}/{len(results)}",
    )

    print(
        "\nNote:"
        "\nA FAIL is an evaluation finding, "
        "not a reason to alter the result."
    )

    print(
        "\n2G evaluation complete."
    )


if __name__ == "__main__":
    main()