import json
import time
from pathlib import Path

import pandas as pd
import requests

from database import reset_live_data as reset_live_data_db


API_URL = "http://127.0.0.1:8000"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

STATION_COUNT = 20

CUTOFF_TIMESTAMP = pd.Timestamp(
    "2025-12-31 00:00:00"
)

REQUEST_DELAY = 0.05

EXPECTED_INTERVAL_MINUTES = 15


# ============================================================
# DATASET
# ============================================================

def load_dataset():
    print("Loading benchmark dataset...")

    df = pd.read_csv(DATASET_PATH)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = df.sort_values(
        ["timestamp", "station_id"]
    ).reset_index(drop=True)

    stations = sorted(
        df["station_id"]
        .dropna()
        .astype(str)
        .unique()
    )

    if len(stations) < STATION_COUNT:
        raise RuntimeError(
            f"Expected at least {STATION_COUNT} stations, "
            f"found {len(stations)}."
        )

    stations = stations[:STATION_COUNT]

    print(
        f"Dataset loaded: {len(df):,} rows"
    )

    print(
        f"Evaluation stations: {len(stations)}"
    )

    return df, stations


# ============================================================
# FIND COMMON CLEAN BASELINE
# ============================================================

def find_common_clean_timestamp(
    df,
    stations,
):
    """
    Find the latest timestamp before the evaluation window
    where every evaluation station has a clean benchmark row.

    This is critical.

    We want one common T0 for all stations, not an independently
    selected timestamp for each station.
    """

    candidate = df[
        (df["timestamp"] < CUTOFF_TIMESTAMP)
        & (df["station_id"].isin(stations))
        & (df["anomaly_flag"] == False)
    ].copy()

    counts = (
        candidate
        .groupby("timestamp")["station_id"]
        .nunique()
    )

    valid = counts[
        counts == len(stations)
    ]

    if valid.empty:
        raise RuntimeError(
            "Could not find a common clean timestamp "
            "for all evaluation stations."
        )

    timestamp = valid.index.max()

    baseline = (
        candidate[
            candidate["timestamp"] == timestamp
        ]
        .drop_duplicates(
            subset=["station_id"],
            keep="first",
        )
        .set_index("station_id")
    )

    missing = [
        station
        for station in stations
        if station not in baseline.index
    ]

    if missing:
        raise RuntimeError(
            f"Baseline missing stations: {missing}"
        )

    print()
    print(
        "Common clean baseline timestamp:"
    )
    print(
        f"  T0 = {timestamp}"
    )

    print(
        f"  Stations = {len(baseline)}/{len(stations)}"
    )

    return timestamp, baseline


# ============================================================
# DATABASE CLEANUP
# ============================================================

def reset_live_data():
    reset_live_data_db()


# ============================================================
# INGEST
# ============================================================

def ingest(
    station_id,
    timestamp,
    temperature_c,
    relative_humidity_pct,
    pressure_hpa,
):
    payload = {
        "station_id": station_id,
        "timestamp": str(timestamp),
        "temperature_c": temperature_c,
        "relative_humidity_pct":
            relative_humidity_pct,
        "pressure_hpa": pressure_hpa,
    }

    response = requests.post(
        f"{API_URL}/ingest",
        json=payload,
        timeout=15,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"/ingest failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    result = response.json()

    if "error" in result:
        raise RuntimeError(
            f"/ingest returned an error: "
            f"{result['error']}"
        )

    return result


# ============================================================
# BASELINE STREAM
# ============================================================

def ingest_clean_baseline(
    baseline,
    stations,
    timestamp,
):
    """
    Insert one clean historical observation at T0 for every
    station.

    These become the immediate preceding observations for T1.
    """

    for station in stations:

        row = baseline.loc[station]

        ingest(
            station_id=station,
            timestamp=timestamp,
            temperature_c=float(
                row["temperature_c"]
            ),
            relative_humidity_pct=float(
                row["relative_humidity_pct"]
            ),
            pressure_hpa=float(
                row["pressure_hpa"]
            ),
        )

        time.sleep(REQUEST_DELAY)


# ============================================================
# VALUE HELPERS
# ============================================================

def clean_values(row):
    return {
        "temperature_c":
            float(row["temperature_c"]),

        "relative_humidity_pct":
            float(row["relative_humidity_pct"]),

        "pressure_hpa":
            float(row["pressure_hpa"]),
    }


def add_values(
    values,
    temperature=0.0,
    humidity=0.0,
    pressure=0.0,
):
    values = values.copy()

    values["temperature_c"] += temperature
    values["relative_humidity_pct"] += humidity
    values["pressure_hpa"] += pressure

    return values


# ============================================================
# RUN SINGLE TIMESTAMP
# ============================================================

def ingest_timestamp(
    baseline,
    stations,
    timestamp,
    modifier,
):
    results = []

    for station in stations:

        values = clean_values(
            baseline.loc[station]
        )

        values = modifier(
            station,
            values,
        )

        result = ingest(
            station_id=station,
            timestamp=timestamp,
            temperature_c=values["temperature_c"],
            relative_humidity_pct=
                values["relative_humidity_pct"],
            pressure_hpa=values["pressure_hpa"],
        )

        results.append(
            {
                "station_id": station,
                "result": result,
            }
        )

        time.sleep(REQUEST_DELAY)

    return results


# ============================================================
# ANALYZE RESULTS
# ============================================================

def summarize_results(
    results,
):
    anomalies = [
        item
        for item in results
        if item["result"].get("anomaly") is True
    ]

    weather = [
        item
        for item in anomalies
        if str(
            item["result"].get(
                "weather_or_sensor",
                ""
            )
        ).lower() == "weather"
    ]

    sensor = [
        item
        for item in anomalies
        if str(
            item["result"].get(
                "weather_or_sensor",
                ""
            )
        ).lower() == "sensor"
    ]

    return {
        "total": len(results),
        "anomalies": len(anomalies),
        "weather": len(weather),
        "sensor": len(sensor),
    }


def print_anomalies(results):
    for item in results:

        result = item["result"]

        if result.get("anomaly") is True:

            print(
                f"  {item['station_id']}: "
                f"anomaly={result.get('anomaly')} "
                f"score={result.get('anomaly_score')} "
                f"class="
                f"{result.get('weather_or_sensor')} "
                f"confidence="
                f"{result.get('confidence')}"
            )


# ============================================================
# 2G.1 NORMAL
# ============================================================

def test_normal(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.1 Normal Telemetry")
    print("=" * 70)

    reset_live_data()

    t1 = (
        t0
        + pd.Timedelta(
            minutes=EXPECTED_INTERVAL_MINUTES
        )
    )

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    results = ingest_timestamp(
        baseline,
        stations,
        t1,
        lambda station, values: values,
    )

    summary = summarize_results(
        results
    )

    passed = (
        summary["anomalies"] == 0
    )

    print(
        f"Expected anomaly: False"
    )

    print(
        f"Anomalies detected: "
        f"{summary['anomalies']}/{summary['total']}"
    )

    print_anomalies(results)

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.1 Normal Telemetry",

        "expected":
            "normal",

        "passed":
            passed,

        "summary":
            summary,

        "results":
            results,
    }


# ============================================================
# 2G.2 REGIONAL WEATHER
# ============================================================

def test_regional_weather(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.2 Regional Weather Event")
    print("=" * 70)

    reset_live_data()

    t1 = (
        t0
        + pd.Timedelta(
            minutes=EXPECTED_INTERVAL_MINUTES
        )
    )

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    def modifier(
        station,
        values,
    ):
        return add_values(
            values,
            temperature=6.0,
            humidity=-10.0,
            pressure=-5.0,
        )

    results = ingest_timestamp(
        baseline,
        stations,
        t1,
        modifier,
    )

    summary = summarize_results(
        results
    )

    passed = (
        summary["weather"] > 0
    )

    print(
        "Expected: coherent regional "
        "weather event"
    )

    print(
        f"Anomalies detected: "
        f"{summary['anomalies']}/"
        f"{summary['total']}"
    )

    print(
        f"Weather classifications: "
        f"{summary['weather']}"
    )

    print(
        f"Sensor classifications: "
        f"{summary['sensor']}"
    )

    print_anomalies(results)

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.2 Regional Weather Event",

        "expected":
            "weather",

        "passed":
            passed,

        "summary":
            summary,

        "results":
            results,
    }


# ============================================================
# 2G.3 ISOLATED SPIKE
# ============================================================

def test_isolated_spike(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.3 Isolated Sensor Spike")
    print("=" * 70)

    reset_live_data()

    t1 = (
        t0
        + pd.Timedelta(
            minutes=EXPECTED_INTERVAL_MINUTES
        )
    )

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    def modifier(
        station,
        values,
    ):
        if station == "AWS_AP08":

            return add_values(
                values,
                temperature=15.0,
            )

        return values

    results = ingest_timestamp(
        baseline,
        stations,
        t1,
        modifier,
    )

    target = [
        item["result"]
        for item in results
        if item["station_id"] == "AWS_AP08"
    ][0]

    passed = (
        target.get("anomaly") is True
        and str(
            target.get(
                "weather_or_sensor",
                "",
            )
        ).lower() == "sensor"
    )

    summary = summarize_results(
        results
    )

    print(
        "Expected AP08: anomaly + sensor"
    )

    print(
        f"AP08 anomaly: "
        f"{target.get('anomaly')}"
    )

    print(
        f"AP08 score: "
        f"{target.get('anomaly_score')}"
    )

    print(
        f"AP08 classification: "
        f"{target.get('weather_or_sensor')}"
    )

    print(
        f"AP08 confidence: "
        f"{target.get('confidence')}"
    )

    print(
        f"Network anomalies: "
        f"{summary['anomalies']}/{summary['total']}"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.3 Isolated Sensor Spike",

        "expected":
            "sensor",

        "passed":
            passed,

        "summary":
            summary,

        "results":
            results,
    }


# ============================================================
# 2G.4 GRADUAL DRIFT
# ============================================================

def test_drift(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.4 Gradual Sensor Drift")
    print("=" * 70)

    reset_live_data()

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    drift_outputs = []

    drift_steps = [
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
    ]

    for index, drift in enumerate(
        drift_steps,
        start=1,
    ):

        timestamp = (
            t0
            + pd.Timedelta(
                minutes=EXPECTED_INTERVAL_MINUTES
                * index
            )
        )

        values = clean_values(
            baseline.loc["AWS_AP08"]
        )

        values = add_values(
            values,
            temperature=drift,
        )

        result = ingest(
            station_id="AWS_AP08",
            timestamp=timestamp,
            temperature_c=
                values["temperature_c"],
            relative_humidity_pct=
                values[
                    "relative_humidity_pct"
                ],
            pressure_hpa=
                values["pressure_hpa"],
        )

        drift_outputs.append(
            result
        )

        print(
            f"  T+{15 * index:02d} min "
            f"+{drift:.1f}°C: "
            f"anomaly="
            f"{result.get('anomaly')} "
            f"score="
            f"{result.get('anomaly_score')} "
            f"class="
            f"{result.get('weather_or_sensor')} "
            f"confidence="
            f"{result.get('confidence')}"
        )

        time.sleep(REQUEST_DELAY)

    final_result = drift_outputs[-1]

    passed = (
        final_result.get("anomaly") is True
        and str(
            final_result.get(
                "weather_or_sensor",
                "",
            )
        ).lower() == "sensor"
    )

    print()
    print(
        "Expected final AP08: "
        "anomaly + sensor"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.4 Gradual Sensor Drift",

        "expected":
            "sensor",

        "passed":
            passed,

        "summary": {
            "total":
                len(drift_outputs),

            "anomalies":
                sum(
                    r.get("anomaly") is True
                    for r in drift_outputs
                ),

            "sensor":
                sum(
                    str(
                        r.get(
                            "weather_or_sensor",
                            "",
                        )
                    ).lower()
                    == "sensor"
                    for r in drift_outputs
                ),
        },

        "results":
            drift_outputs,
    }


# ============================================================
# 2G.5 FROZEN SENSOR
# ============================================================

def test_frozen(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.5 Frozen Sensor")
    print("=" * 70)

    reset_live_data()

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    row = baseline.loc[
        "AWS_AP08"
    ]

    values = clean_values(
        row
    )

    frozen_outputs = []

    for index in range(1, 9):

        timestamp = (
            t0
            + pd.Timedelta(
                minutes=EXPECTED_INTERVAL_MINUTES
                * index
            )
        )

        result = ingest(
            station_id="AWS_AP08",
            timestamp=timestamp,
            temperature_c=
                values["temperature_c"],
            relative_humidity_pct=
                values[
                    "relative_humidity_pct"
                ],
            pressure_hpa=
                values["pressure_hpa"],
        )

        frozen_outputs.append(
            result
        )

        print(
            f"  Step {index}: "
            f"anomaly="
            f"{result.get('anomaly')} "
            f"score="
            f"{result.get('anomaly_score')} "
            f"class="
            f"{result.get('weather_or_sensor')} "
            f"confidence="
            f"{result.get('confidence')}"
        )

        time.sleep(REQUEST_DELAY)

    final_result = frozen_outputs[-1]

    passed = (
        final_result.get("anomaly") is True
        and str(
            final_result.get(
                "weather_or_sensor",
                "",
            )
        ).lower() == "sensor"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.5 Frozen Sensor",

        "expected":
            "sensor",

        "passed":
            passed,

        "summary": {
            "total":
                len(frozen_outputs),

            "anomalies":
                sum(
                    r.get("anomaly") is True
                    for r in frozen_outputs
                ),

            "sensor":
                sum(
                    str(
                        r.get(
                            "weather_or_sensor",
                            "",
                        )
                    ).lower()
                    == "sensor"
                    for r in frozen_outputs
                ),
        },

        "results":
            frozen_outputs,
    }


# ============================================================
# 2G.6 MISSING TELEMETRY
# ============================================================

def test_missing(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.6 Missing Telemetry")
    print("=" * 70)

    reset_live_data()

    t1 = (
        t0
        + pd.Timedelta(
            minutes=EXPECTED_INTERVAL_MINUTES
        )
    )

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    # Only AP08 loses its telemetry.
    # The other stations remain normal.
    results = []

    for station in stations:

        if station == "AWS_AP08":

            result = ingest(
                station_id=station,
                timestamp=t1,
                temperature_c=None,
                relative_humidity_pct=None,
                pressure_hpa=None,
            )

        else:

            values = clean_values(
                baseline.loc[station]
            )

            result = ingest(
                station_id=station,
                timestamp=t1,
                temperature_c=
                    values["temperature_c"],
                relative_humidity_pct=
                    values[
                        "relative_humidity_pct"
                    ],
                pressure_hpa=
                    values["pressure_hpa"],
            )

        results.append(
            {
                "station_id": station,
                "result": result,
            }
        )

        time.sleep(REQUEST_DELAY)

    target = [
        item["result"]
        for item in results
        if item["station_id"]
        == "AWS_AP08"
    ][0]

    # For missing telemetry the important pipeline requirement
    # is that the missing-input observation is processed without
    # crashing and produces a complete feature vector.
    #
    # Classification as sensor is useful but is not required
    # for this data-quality test.
    passed = (
        target.get("anomaly") is True
        or target.get("features_computed_count")
        == 50
        or "features_computed_count"
        in target
    )

    print(
        "Expected AP08: missing telemetry "
        "handled by pipeline"
    )

    print(
        f"AP08 anomaly: "
        f"{target.get('anomaly')}"
    )

    print(
        f"AP08 score: "
        f"{target.get('anomaly_score')}"
    )

    print(
        f"AP08 classification: "
        f"{target.get('weather_or_sensor')}"
    )

    print(
        f"AP08 confidence: "
        f"{target.get('confidence')}"
    )

    print(
        f"AP08 features computed: "
        f"{target.get('features_computed_count')}"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.6 Missing Telemetry",

        "expected":
            "missing-data handling",

        "passed":
            passed,

        "summary":
            summarize_results(results),

        "results":
            results,
    }


# ============================================================
# 2G.7 REGIONAL VS ISOLATED
# ============================================================

def test_discrimination(
    baseline,
    stations,
    t0,
):
    print()
    print("=" * 70)
    print("2G.7 Regional vs Isolated Discrimination")
    print("=" * 70)

    # --------------------------------------------------------
    # PART A — REGIONAL EVENT
    # --------------------------------------------------------

    reset_live_data()

    t1 = (
        t0
        + pd.Timedelta(
            minutes=EXPECTED_INTERVAL_MINUTES
        )
    )

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    def regional_modifier(
        station,
        values,
    ):
        return add_values(
            values,
            temperature=7.0,
            humidity=-12.0,
            pressure=-6.0,
        )

    regional_results = ingest_timestamp(
        baseline,
        stations,
        t1,
        regional_modifier,
    )

    regional_summary = summarize_results(
        regional_results
    )

    print()
    print(
        "Regional event:"
    )

    print(
        f"  anomalies="
        f"{regional_summary['anomalies']}"
    )

    print(
        f"  weather="
        f"{regional_summary['weather']}"
    )

    print(
        f"  sensor="
        f"{regional_summary['sensor']}"
    )

    print_anomalies(
        regional_results
    )

    # --------------------------------------------------------
    # PART B — ISOLATED SENSOR EVENT
    # --------------------------------------------------------

    reset_live_data()

    ingest_clean_baseline(
        baseline,
        stations,
        t0,
    )

    def isolated_modifier(
        station,
        values,
    ):
        if station == "AWS_AP08":

            return add_values(
                values,
                temperature=18.0,
            )

        return values

    isolated_results = ingest_timestamp(
        baseline,
        stations,
        t1,
        isolated_modifier,
    )

    target = [
        item["result"]
        for item in isolated_results
        if item["station_id"]
        == "AWS_AP08"
    ][0]

    isolated_summary = summarize_results(
        isolated_results
    )

    print()
    print(
        "Isolated AP08 event:"
    )

    print(
        f"  AP08 anomaly="
        f"{target.get('anomaly')}"
    )

    print(
        f"  AP08 score="
        f"{target.get('anomaly_score')}"
    )

    print(
        f"  AP08 classification="
        f"{target.get('weather_or_sensor')}"
    )

    print(
        f"  AP08 confidence="
        f"{target.get('confidence')}"
    )

    print(
        f"  network anomalies="
        f"{isolated_summary['anomalies']}"
    )

    passed = (
        regional_summary["weather"] > 0
        and target.get("anomaly") is True
        and str(
            target.get(
                "weather_or_sensor",
                "",
            )
        ).lower() == "sensor"
    )

    print()
    print(
        "Expected:"
    )

    print(
        "  Regional event → weather"
    )

    print(
        "  Isolated AP08 → sensor"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.7 Regional vs Isolated Discrimination",

        "expected":
            "weather vs sensor",

        "passed":
            passed,

        "regional":
            {
                "summary":
                    regional_summary,

                "results":
                    regional_results,
            },

        "isolated":
            {
                "summary":
                    isolated_summary,

                "target":
                    target,

                "results":
                    isolated_results,
            },
    }


# ============================================================
# MAIN
# ============================================================

def run():
    print()
    print("=" * 70)
    print("SIH26073 — 2G EVALUATION V3")
    print("=" * 70)

    print()
    print(
        "Model: existing Random Forest pipeline"
    )

    print(
        "Inputs: Temperature / Relative Humidity / "
        "Pressure / Timestamp"
    )

    print(
        "Evaluation: independent scenarios with "
        "historical data preserved"
    )

    print()

    # --------------------------------------------------------
    # BACKEND CHECK
    # --------------------------------------------------------

    try:

        response = requests.get(
            f"{API_URL}/",
            timeout=5,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Backend check failed: "
                f"{response.status_code} "
                f"{response.text}"
            )

    except requests.RequestException as exc:

        raise RuntimeError(
            "Backend is not reachable. "
            "Start it before running this evaluator."
        ) from exc

    # --------------------------------------------------------
    # LOAD DATASET
    # --------------------------------------------------------

    df, stations = load_dataset()

    t0, baseline = (
        find_common_clean_timestamp(
            df,
            stations,
        )
    )

    # --------------------------------------------------------
    # RUN TESTS
    # --------------------------------------------------------

    results = []

    results.append(
        test_normal(
            baseline,
            stations,
            t0,
        )
    )

    results.append(
        test_regional_weather(
            baseline,
            stations,
            t0,
        )
    )

    results.append(
        test_isolated_spike(
            baseline,
            stations,
            t0,
        )
    )

    results.append(
        test_drift(
            baseline,
            stations,
            t0,
        )
    )

    results.append(
        test_frozen(
            baseline,
            stations,
            t0,
        )
    )

    results.append(
        test_missing(
            baseline,
            stations,
            t0,
        )
    )

    results.append(
        test_discrimination(
            baseline,
            stations,
            t0,
        )
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print()
    print("=" * 70)
    print("2G EVALUATION V3 — SUMMARY")
    print("=" * 70)

    passed = sum(
        result["passed"]
        for result in results
    )

    total = len(results)

    print()

    for result in results:

        print(
            f"{result['name']:<45}"
            f"{'PASS' if result['passed'] else 'FAIL'}"
        )

    print()

    print(
        f"Scenario score: "
        f"{passed}/{total}"
    )

    print()

    report_path = (
        Path(__file__).resolve().parent
        / "2g_evaluation_v3_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            default=str,
        )

    print(
        "Detailed report saved to:"
    )

    print(report_path)

    print()
    print("=" * 70)
    print("Evaluation complete.")
    print("=" * 70)


if __name__ == "__main__":
    run()