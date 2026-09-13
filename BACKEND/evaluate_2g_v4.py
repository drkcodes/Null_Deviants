import json
import math
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

EVALUATION_START = pd.Timestamp(
    "2025-12-31 00:00:00"
)

EXPECTED_INTERVAL_MINUTES = 15

REQUEST_DELAY = 0.05

TARGET_STATION = "AWS_AP08"

EPSILON = 1e-9


# ============================================================
# DATASET
# ============================================================

def load_dataset():
    print("Loading benchmark dataset...")

    df = pd.read_csv(DATASET_PATH)

    required_columns = [
        "timestamp",
        "station_id",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise RuntimeError(
            f"Dataset is missing required columns: "
            f"{missing_columns}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df["station_id"] = (
        df["station_id"]
        .astype(str)
    )

    df = df.sort_values(
        ["timestamp", "station_id"]
    ).reset_index(drop=True)

    stations = sorted(
        df["station_id"]
        .dropna()
        .unique()
    )

    if len(stations) < STATION_COUNT:
        raise RuntimeError(
            f"Expected at least {STATION_COUNT} "
            f"stations, found {len(stations)}."
        )

    stations = stations[:STATION_COUNT]

    if TARGET_STATION not in stations:
        raise RuntimeError(
            f"Target station {TARGET_STATION} "
            f"is not present in evaluation stations."
        )

    print(
        f"Dataset loaded: {len(df):,} rows"
    )

    print(
        f"Evaluation stations: {len(stations)}"
    )

    print(
        f"Evaluation window starts: "
        f"{EVALUATION_START}"
    )

    return df, stations


# ============================================================
# DATASET SNAPSHOTS
# ============================================================

def build_snapshot(
    df,
    stations,
    timestamp,
):
    """
    Return one complete contemporaneous 20-station
    benchmark snapshot.

    Only actual dataset values are used.
    """

    rows = df[
        (df["timestamp"] == timestamp)
        & (df["station_id"].isin(stations))
    ].copy()

    rows = (
        rows
        .drop_duplicates(
            subset=["station_id"],
            keep="first",
        )
        .set_index("station_id")
    )

    missing = [
        station
        for station in stations
        if station not in rows.index
    ]

    if missing:
        raise RuntimeError(
            f"Timestamp {timestamp} is missing "
            f"stations: {missing}"
        )

    return rows.loc[stations]


def find_previous_common_timestamp(
    df,
    stations,
    timestamp,
):
    """
    Find the latest timestamp before `timestamp`
    containing all evaluation stations.
    """

    candidate_times = sorted(
        df[
            (df["timestamp"] < timestamp)
            & (df["station_id"].isin(stations))
        ]["timestamp"]
        .unique()
    )

    for candidate in reversed(candidate_times):

        try:
            snapshot = build_snapshot(
                df,
                stations,
                candidate,
            )

            if len(snapshot) == len(stations):
                return candidate, snapshot

        except RuntimeError:
            continue

    raise RuntimeError(
        f"Could not find a complete common "
        f"timestamp before {timestamp}."
    )


def get_sequential_timestamps(
    df,
    stations,
    start_timestamp,
    count,
):
    """
    Get `count` consecutive complete benchmark
    timestamps beginning at start_timestamp.
    """

    timestamps = sorted(
        df[
            (df["timestamp"] >= start_timestamp)
            & (df["station_id"].isin(stations))
        ]["timestamp"]
        .unique()
    )

    complete = []

    for timestamp in timestamps:

        try:
            build_snapshot(
                df,
                stations,
                timestamp,
            )

            complete.append(timestamp)

            if len(complete) >= count:
                break

        except RuntimeError:
            continue

    if len(complete) < count:
        raise RuntimeError(
            f"Could only find {len(complete)} "
            f"complete timestamps; required {count}."
        )

    # Verify actual 15-minute cadence.
    for previous, current in zip(
        complete,
        complete[1:],
    ):

        delta_minutes = (
            pd.Timestamp(current)
            - pd.Timestamp(previous)
        ).total_seconds() / 60.0

        if abs(
            delta_minutes
            - EXPECTED_INTERVAL_MINUTES
        ) > EPSILON:

            raise RuntimeError(
                "Evaluation timestamps are not "
                f"15 minutes apart: "
                f"{previous} -> {current}"
            )

    return complete


# ============================================================
# DATABASE CLEANUP
# ============================================================

def reset_live_data():
    reset_live_data_db()


# ============================================================
# BACKEND CHECK
# ============================================================

def check_backend():
    print()
    print("Checking backend...")

    try:

        response = requests.get(
            f"{API_URL}/",
            timeout=5,
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            "Backend is not reachable. "
            "Start Uvicorn before running the evaluator."
        ) from exc

    if response.status_code != 200:

        raise RuntimeError(
            f"Backend health check failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    print("Backend: OK")


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


def modify_values(
    values,
    temperature=0.0,
    humidity=0.0,
    pressure=0.0,
):
    result = values.copy()

    result["temperature_c"] += temperature
    result["relative_humidity_pct"] += humidity
    result["pressure_hpa"] += pressure

    return result


def is_anomaly(result):
    return result.get("anomaly") is True


def classification(result):
    return str(
        result.get(
            "weather_or_sensor",
            "",
        )
    ).strip().lower()


# ============================================================
# BATCH INGEST
# ============================================================

def ingest_batch(
    stations,
    timestamp,
    snapshot,
    modifier=None,
):
    """
    Send all stations for one timestamp in a single
    /ingest/batch request.

    This is important because the spatial features must
    compare contemporaneous observations.
    """

    readings = []

    for station in stations:

        values = clean_values(
            snapshot.loc[station]
        )

        if modifier is not None:

            values = modifier(
                station,
                values,
            )

        readings.append(
            {
                "station_id": station,
                "timestamp": str(timestamp),
                "temperature_c":
                    values["temperature_c"],
                "relative_humidity_pct":
                    values[
                        "relative_humidity_pct"
                    ],
                "pressure_hpa":
                    values["pressure_hpa"],
            }
        )

    payload = {
        "readings": readings
    }

    response = requests.post(
        f"{API_URL}/ingest/batch",
        json=payload,
        timeout=30,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"/ingest/batch failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    result = response.json()

    if "error" in result:

        raise RuntimeError(
            f"/ingest/batch returned error: "
            f"{result['error']}"
        )

    if result.get("stations_processed") != len(
        stations
    ):

        raise RuntimeError(
            "Batch did not process all stations: "
            f"{result.get('stations_processed')}/"
            f"{len(stations)}"
        )

    results = result.get(
        "results",
        [],
    )

    if len(results) != len(stations):

        raise RuntimeError(
            "Batch returned an unexpected number "
            f"of results: {len(results)}"
        )

    return results


# ============================================================
# RESULT HELPERS
# ============================================================

def summarize_results(results):
    anomalies = [
        result
        for result in results
        if is_anomaly(result)
    ]

    weather = [
        result
        for result in anomalies
        if classification(result)
        == "weather"
    ]

    sensor = [
        result
        for result in anomalies
        if classification(result)
        == "sensor"
    ]

    return {
        "total": len(results),
        "anomalies": len(anomalies),
        "weather": len(weather),
        "sensor": len(sensor),
    }


def get_result_for_station(
    results,
    station,
):
    matches = [
        result
        for result in results
        if result.get("station_id")
        == station
    ]

    if not matches:
        raise RuntimeError(
            f"No result returned for {station}"
        )

    return matches[0]


def print_anomalies(results):
    for result in results:

        if not is_anomaly(result):
            continue

        print(
            f"  {result.get('station_id')}: "
            f"anomaly={result.get('anomaly')} "
            f"score={result.get('anomaly_score')} "
            f"class={result.get('weather_or_sensor')} "
            f"confidence={result.get('confidence')}"
        )


def print_target_result(
    result,
    station=TARGET_STATION,
):
    print(
        f"  {station}: "
        f"anomaly={result.get('anomaly')} "
        f"score={result.get('anomaly_score')} "
        f"class={result.get('weather_or_sensor')} "
        f"confidence={result.get('confidence')}"
    )


# ============================================================
# SCENARIO MODIFIERS
# ============================================================

def normal_modifier(
    station,
    values,
):
    return values


def regional_weather_modifier(
    station,
    values,
):
    """
    Strong but coherent atmospheric event.

    Every station receives the same perturbation,
    therefore spatial consistency should indicate
    a regional event rather than an isolated sensor fault.
    """

    return modify_values(
        values,
        temperature=6.0,
        humidity=-10.0,
        pressure=-5.0,
    )


def isolated_spike_modifier(
    station,
    values,
):
    if station == TARGET_STATION:

        return modify_values(
            values,
            temperature=15.0,
        )

    return values


def isolated_strong_spike_modifier(
    station,
    values,
):
    if station == TARGET_STATION:

        return modify_values(
            values,
            temperature=18.0,
        )

    return values


# ============================================================
# 2G.1 NORMAL TELEMETRY
# ============================================================

def test_normal(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.1 Normal Telemetry")
    print("=" * 70)

    reset_live_data()

    # Use actual sequential benchmark observations.
    t0 = timestamps[0]
    t1 = timestamps[1]

    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    snapshot_t1 = build_snapshot(
        df,
        stations,
        t1,
    )

    # T0 establishes the actual previous observation.
    results_t0 = ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    time.sleep(REQUEST_DELAY)

    results_t1 = ingest_batch(
        stations,
        t1,
        snapshot_t1,
        normal_modifier,
    )

    summary = summarize_results(
        results_t1
    )

    # This is a false-alarm measurement, not a claim
    # that the synthetic dataset is physically perfect.
    passed = (
        summary["anomalies"] == 0
    )

    print(
        f"T0: {t0}"
    )

    print(
        f"T1: {t1}"
    )

    print(
        "Expected: normal benchmark telemetry"
    )

    print(
        f"Anomalies at T1: "
        f"{summary['anomalies']}/"
        f"{summary['total']}"
    )

    print_anomalies(
        results_t1
    )

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

        "timestamps":
            [
                str(t0),
                str(t1),
            ],

        "summary":
            summary,

        "results":
            results_t1,
    }


# ============================================================
# 2G.2 REGIONAL WEATHER
# ============================================================

def test_regional_weather(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.2 Regional Weather Event")
    print("=" * 70)

    reset_live_data()

    t0 = timestamps[0]
    t1 = timestamps[1]

    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    snapshot_t1 = build_snapshot(
        df,
        stations,
        t1,
    )

    # Actual clean preceding observations.
    ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    time.sleep(REQUEST_DELAY)

    # Actual T1 values + coherent regional event.
    results = ingest_batch(
        stations,
        t1,
        snapshot_t1,
        regional_weather_modifier,
    )

    summary = summarize_results(
        results
    )

    passed = (
        summary["weather"] > 0
        and summary["sensor"] == 0
    )

    print(
        f"T0: {t0}"
    )

    print(
        f"T1: {t1}"
    )

    print(
        "Injected event: +6°C, -10% RH, -5 hPa "
        "at every station"
    )

    print(
        "Expected: coherent regional event → weather"
    )

    print(
        f"Anomalies: "
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

    print_anomalies(
        results
    )

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

        "timestamp":
            str(t1),

        "injection": {
            "temperature_delta_c":
                6.0,

            "humidity_delta_pct":
                -10.0,

            "pressure_delta_hpa":
                -5.0,

            "stations":
                len(stations),
        },

        "summary":
            summary,

        "results":
            results,
    }


# ============================================================
# 2G.3 ISOLATED SENSOR SPIKE
# ============================================================

def test_isolated_spike(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.3 Isolated Sensor Spike")
    print("=" * 70)

    reset_live_data()

    t0 = timestamps[0]
    t1 = timestamps[1]

    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    snapshot_t1 = build_snapshot(
        df,
        stations,
        t1,
    )

    ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    time.sleep(REQUEST_DELAY)

    results = ingest_batch(
        stations,
        t1,
        snapshot_t1,
        isolated_spike_modifier,
    )

    target = get_result_for_station(
        results,
        TARGET_STATION,
    )

    summary = summarize_results(
        results
    )

    passed = (
        is_anomaly(target)
        and classification(target)
        == "sensor"
    )

    print(
        f"T0: {t0}"
    )

    print(
        f"T1: {t1}"
    )

    print(
        "Injected AP08 temperature spike: +15°C"
    )

    print(
        "Expected AP08: anomaly + sensor"
    )

    print_target_result(
        target
    )

    print(
        f"Network anomalies: "
        f"{summary['anomalies']}/"
        f"{summary['total']}"
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

        "timestamp":
            str(t1),

        "target":
            TARGET_STATION,

        "injection": {
            "temperature_delta_c":
                15.0,
        },

        "summary":
            summary,

        "target_result":
            target,

        "results":
            results,
    }


# ============================================================
# 2G.4 GRADUAL SENSOR DRIFT
# ============================================================

def test_drift(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.4 Gradual Sensor Drift")
    print("=" * 70)

    reset_live_data()

    # We need T0 + five subsequent actual observations.
    if len(timestamps) < 6:

        raise RuntimeError(
            "Drift test requires at least "
            "6 sequential timestamps."
        )

    drift_steps = [
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
    ]

    t0 = timestamps[0]
    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    # Establish the actual clean observation before applying drift.
    results_t0 = ingest_batch(
        stations,
        t0,
        snapshot_t0,
    )

    assert len(results_t0) == len(stations), (
        "T0 batch was not accepted for every station: "
        f"{len(results_t0)}/{len(stations)}"
    )

    t0_result = get_result_for_station(
        results_t0,
        TARGET_STATION,
    )

    assert t0_result.get("timestamp", "").startswith(
        str(t0).replace(" ", "T")
    ), "T0 response did not contain the requested timestamp."

    print(
        f"T0 accepted and persisted: {t0} "
        f"({len(results_t0)}/{len(stations)} stations)"
    )

    time.sleep(
        REQUEST_DELAY
    )

    outputs = []

    for index, drift in enumerate(
        drift_steps,
        start=1,
    ):

        timestamp = timestamps[index]

        snapshot = build_snapshot(
            df,
            stations,
            timestamp,
        )

        def modifier(
            station,
            values,
            drift=drift,
        ):
            if station == TARGET_STATION:

                return modify_values(
                    values,
                    temperature=drift,
                )

            return values

        results = ingest_batch(
            stations,
            timestamp,
            snapshot,
            modifier,
        )

        target = get_result_for_station(
            results,
            TARGET_STATION,
        )

        outputs.append(
            {
                "timestamp":
                    str(timestamp),

                "drift_c":
                    drift,

                "result":
                    target,
            }
        )

        print(
            f"  T+{15 * index:02d} min "
            f"AP08 drift=+{drift:.1f}°C "
            f"anomaly={target.get('anomaly')} "
            f"score={target.get('anomaly_score')} "
            f"class={target.get('weather_or_sensor')} "
            f"confidence={target.get('confidence')}"
        )

        time.sleep(
            REQUEST_DELAY
        )

    anomalies = [
        item
        for item in outputs
        if is_anomaly(item["result"])
    ]

    sensor_anomalies = [
        item
        for item in outputs
        if (
            is_anomaly(item["result"])
            and classification(item["result"])
            == "sensor"
        )
    ]

    passed = (
        len(sensor_anomalies) > 0
    )

    first_detection = None

    if sensor_anomalies:

        first_detection = (
            sensor_anomalies[0]["timestamp"]
        )

    print()

    print(
        "Expected: progressive AP08 drift "
        "eventually detected as sensor"
    )

    print(
        f"Anomaly detections: "
        f"{len(anomalies)}/{len(outputs)}"
    )

    print(
        f"Sensor detections: "
        f"{len(sensor_anomalies)}/{len(outputs)}"
    )

    print(
        f"First sensor detection: "
        f"{first_detection}"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.4 Gradual Sensor Drift",

        "expected":
            "eventual sensor detection",

        "passed":
            passed,

        "first_detection":
            first_detection,

        "steps":
            outputs,

        "summary": {
            "total":
                len(outputs),

            "anomalies":
                len(anomalies),

            "sensor":
                len(sensor_anomalies),
        },
    }


# ============================================================
# 2G.5 FROZEN SENSOR
# ============================================================

def test_frozen(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.5 Frozen Sensor")
    print("=" * 70)

    reset_live_data()

    if len(timestamps) < 9:

        raise RuntimeError(
            "Frozen test requires at least "
            "9 sequential timestamps."
        )

    # T0 is the actual last clean observation.
    t0 = timestamps[0]

    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    # AP08 is frozen at its T0 values.
    frozen_values = clean_values(
        snapshot_t0.loc[TARGET_STATION]
    )

    outputs = []

    for index in range(1, 9):

        timestamp = timestamps[index]

        snapshot = build_snapshot(
            df,
            stations,
            timestamp,
        )

        def modifier(
            station,
            values,
        ):
            if station == TARGET_STATION:

                return frozen_values.copy()

            return values

        results = ingest_batch(
            stations,
            timestamp,
            snapshot,
            modifier,
        )

        target = get_result_for_station(
            results,
            TARGET_STATION,
        )

        outputs.append(
            {
                "timestamp":
                    str(timestamp),

                "step":
                    index,

                "result":
                    target,
            }
        )

        print(
            f"  Step {index}: "
            f"T={timestamp} "
            f"anomaly={target.get('anomaly')} "
            f"score={target.get('anomaly_score')} "
            f"class={target.get('weather_or_sensor')} "
            f"confidence={target.get('confidence')}"
        )

        time.sleep(
            REQUEST_DELAY
        )

    anomalies = [
        item
        for item in outputs
        if is_anomaly(item["result"])
    ]

    sensor_anomalies = [
        item
        for item in outputs
        if (
            is_anomaly(item["result"])
            and classification(item["result"])
            == "sensor"
        )
    ]

    passed = (
        len(sensor_anomalies) > 0
    )

    first_detection = None

    if sensor_anomalies:

        first_detection = (
            sensor_anomalies[0]["timestamp"]
        )

    print()

    print(
        "Expected: AP08 frozen while the "
        "rest of the network follows actual telemetry"
    )

    print(
        f"Anomaly detections: "
        f"{len(anomalies)}/{len(outputs)}"
    )

    print(
        f"Sensor detections: "
        f"{len(sensor_anomalies)}/{len(outputs)}"
    )

    print(
        f"First sensor detection: "
        f"{first_detection}"
    )

    print(
        f"RESULT: "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "name":
            "2G.5 Frozen Sensor",

        "expected":
            "eventual sensor detection",

        "passed":
            passed,

        "first_detection":
            first_detection,

        "steps":
            outputs,

        "summary": {
            "total":
                len(outputs),

            "anomalies":
                len(anomalies),

            "sensor":
                len(sensor_anomalies),
        },
    }


# ============================================================
# 2G.6 MISSING TELEMETRY
# ============================================================

def test_missing(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.6 Missing Telemetry")
    print("=" * 70)

    reset_live_data()

    t0 = timestamps[0]
    t1 = timestamps[1]

    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    snapshot_t1 = build_snapshot(
        df,
        stations,
        t1,
    )

    ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    # Missing values must be sent only for AP08.
    readings = []

    for station in stations:

        if station == TARGET_STATION:

            readings.append(
                {
                    "station_id":
                        station,

                    "timestamp":
                        str(t1),

                    "temperature_c":
                        None,

                    "relative_humidity_pct":
                        None,

                    "pressure_hpa":
                        None,
                }
            )

        else:

            values = clean_values(
                snapshot_t1.loc[station]
            )

            readings.append(
                {
                    "station_id":
                        station,

                    "timestamp":
                        str(t1),

                    "temperature_c":
                        values[
                            "temperature_c"
                        ],

                    "relative_humidity_pct":
                        values[
                            "relative_humidity_pct"
                        ],

                    "pressure_hpa":
                        values[
                            "pressure_hpa"
                        ],
                }
            )

    response = requests.post(
        f"{API_URL}/ingest/batch",
        json={
            "readings": readings
        },
        timeout=30,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"Missing telemetry batch failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    batch_result = response.json()

    if "error" in batch_result:

        raise RuntimeError(
            f"Missing telemetry returned error: "
            f"{batch_result['error']}"
        )

    results = batch_result.get(
        "results",
        [],
    )

    target = get_result_for_station(
        results,
        TARGET_STATION,
    )

    # Missing-data handling is the core requirement.
    # A successful 20-station batch is itself important.
    features_count = target.get(
        "features_computed_count"
    )

    passed = (
        features_count == 50
        or is_anomaly(target)
    )

    print(
        f"T0: {t0}"
    )

    print(
        f"T1: {t1}"
    )

    print(
        "Injected AP08: T/RH/Pressure = missing"
    )

    print(
        "Expected: pipeline handles missing telemetry"
    )

    print_target_result(
        target
    )

    print(
        f"AP08 features computed: "
        f"{features_count}"
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

        "timestamp":
            str(t1),

        "target":
            TARGET_STATION,

        "target_result":
            target,

        "batch_result":
            batch_result,
    }


# ============================================================
# 2G.7 REGIONAL VS ISOLATED
# ============================================================

def test_discrimination(
    df,
    stations,
    timestamps,
):
    print()
    print("=" * 70)
    print("2G.7 Regional vs Isolated Discrimination")
    print("=" * 70)

    t0 = timestamps[0]
    t1 = timestamps[1]

    # --------------------------------------------------------
    # PART A — REGIONAL
    # --------------------------------------------------------

    reset_live_data()

    snapshot_t0 = build_snapshot(
        df,
        stations,
        t0,
    )

    snapshot_t1 = build_snapshot(
        df,
        stations,
        t1,
    )

    ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    time.sleep(REQUEST_DELAY)

    regional_results = ingest_batch(
        stations,
        t1,
        snapshot_t1,
        regional_weather_modifier,
    )

    regional_summary = summarize_results(
        regional_results
    )

    print()
    print("Regional event:")

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
    # PART B — ISOLATED
    # --------------------------------------------------------

    reset_live_data()

    ingest_batch(
        stations,
        t0,
        snapshot_t0,
        normal_modifier,
    )

    time.sleep(REQUEST_DELAY)

    isolated_results = ingest_batch(
        stations,
        t1,
        snapshot_t1,
        isolated_strong_spike_modifier,
    )

    isolated_summary = summarize_results(
        isolated_results
    )

    target = get_result_for_station(
        isolated_results,
        TARGET_STATION,
    )

    print()
    print("Isolated AP08 event:")

    print_target_result(
        target
    )

    print(
        f"  network anomalies="
        f"{isolated_summary['anomalies']}"
    )

    print(
        f"  weather="
        f"{isolated_summary['weather']}"
    )

    print(
        f"  sensor="
        f"{isolated_summary['sensor']}"
    )

    print()

    print("Expected:")

    print(
        "  Regional event → weather"
    )

    print(
        "  Isolated AP08 event → sensor"
    )

    passed = (
        regional_summary["weather"] > 0
        and regional_summary["sensor"] == 0
        and is_anomaly(target)
        and classification(target)
        == "sensor"
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

        "regional": {
            "summary":
                regional_summary,

            "results":
                regional_results,
        },

        "isolated": {
            "summary":
                isolated_summary,

            "target":
                target,

            "results":
                isolated_results,
        },
    }


# ============================================================
# REPORT
# ============================================================

def save_report(
    results,
    metadata,
):
    report = {
        "evaluation": "SIH26073 2G Evaluation V4",
        "model": "Existing Random Forest pipeline",
        "inputs": [
            "Temperature",
            "Relative Humidity",
            "Atmospheric Pressure",
            "Timestamp",
        ],
        "methodology": metadata,
        "results": results,
    }

    report_path = (
        Path(__file__).resolve().parent
        / "2g_evaluation_v4_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    return report_path


# ============================================================
# MAIN
# ============================================================

def run():
    print()
    print("=" * 70)
    print("SIH26073 — 2G EVALUATION V4")
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
        "Data: actual sequential benchmark observations"
    )

    print(
        "Transport: /ingest/batch "
        "(20-station contemporaneous snapshots)"
    )

    print(
        "Isolation: live data reset between scenarios"
    )

    check_backend()

    df, stations = load_dataset()

    # Need enough timestamps for:
    # normal       = 2
    # regional     = 2
    # isolated     = 2
    # drift        = 6
    # frozen       = 9
    # missing      = 2
    # discrimination = 2
    #
    # Nine consecutive timestamps cover all scenarios.

    timestamps = get_sequential_timestamps(
        df,
        stations,
        EVALUATION_START,
        9,
    )

    print()
    print("Benchmark timestamps selected:")

    for index, timestamp in enumerate(
        timestamps
    ):

        print(
            f"  T{index}: {timestamp}"
        )

    previous_timestamp, _ = (
        find_previous_common_timestamp(
            df,
            stations,
            timestamps[0],
        )
    )

    print()
    print(
        "Historical preceding timestamp:"
    )

    print(
        f"  {previous_timestamp}"
    )

    results = []

    # --------------------------------------------------------
    # 2G.1
    # --------------------------------------------------------

    results.append(
        test_normal(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # 2G.2
    # --------------------------------------------------------

    results.append(
        test_regional_weather(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # 2G.3
    # --------------------------------------------------------

    results.append(
        test_isolated_spike(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # 2G.4
    # --------------------------------------------------------

    results.append(
        test_drift(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # 2G.5
    # --------------------------------------------------------

    results.append(
        test_frozen(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # 2G.6
    # --------------------------------------------------------

    results.append(
        test_missing(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # 2G.7
    # --------------------------------------------------------

    results.append(
        test_discrimination(
            df,
            stations,
            timestamps,
        )
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print()
    print("=" * 70)
    print("2G EVALUATION V4 — SUMMARY")
    print("=" * 70)

    passed = sum(
        bool(result["passed"])
        for result in results
    )

    total = len(results)

    print()

    for result in results:

        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"{result['name']:<48}"
            f"{status}"
        )

    print()

    print(
        f"Scenario score: "
        f"{passed}/{total}"
    )

    metadata = {
        "dataset":
            str(DATASET_PATH),

        "stations":
            stations,

        "station_count":
            len(stations),

        "evaluation_start":
            str(EVALUATION_START),

        "benchmark_timestamps":
            [
                str(timestamp)
                for timestamp in timestamps
            ],

        "historical_preceding_timestamp":
            str(previous_timestamp),

        "transport":
            "/ingest/batch",

        "scenario_isolation":
            "DELETE source='live' between scenarios",

        "model_changed":
            False,

        "threshold_changed":
            False,

        "actual_sequential_dataset_values":
            True,

        "contemporaneous_network_snapshots":
            True,
    }

    report_path = save_report(
        results,
        metadata,
    )

    print()

    print(
        "Detailed report saved to:"
    )

    print(report_path)

    print()
    print("=" * 70)
    print("Evaluation complete.")
    print("=" * 70)

    return results


if __name__ == "__main__":
    run()