import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from database import reset_live_data


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)
API_URL = os.getenv("SIH_API_URL", "http://127.0.0.1:8000").rstrip("/")
REPORT_PATH = Path(__file__).resolve().parent / "injected_evaluation_report.json"

STATION_COUNT = 20
TARGET_STATION = "AWS_AP08"
EVALUATION_START = pd.Timestamp("2025-12-31 00:00:00")
INTERVAL_MINUTES = 15
REQUEST_DELAY_SECONDS = 0.05

REQUIRED_COLUMNS = [
    "timestamp",
    "station_id",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
]


class EvaluationError(RuntimeError):
    pass


def load_dataset():
    print(f"Loading benchmark dataset: {DATASET_PATH}")
    if not DATASET_PATH.exists():
        raise EvaluationError(f"Benchmark dataset not found: {DATASET_PATH}")

    data = pd.read_csv(DATASET_PATH)
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in data.columns
    ]
    if missing_columns:
        raise EvaluationError(
            f"Dataset is missing required columns: {missing_columns}"
        )

    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    if data["timestamp"].isna().any():
        raise EvaluationError("Dataset contains malformed timestamps.")

    data["station_id"] = data["station_id"].astype(str)
    data = data.sort_values(["timestamp", "station_id"]).reset_index(drop=True)

    stations = sorted(data["station_id"].dropna().unique())
    if len(stations) < STATION_COUNT:
        raise EvaluationError(
            f"Expected at least {STATION_COUNT} stations, found {len(stations)}."
        )
    stations = stations[:STATION_COUNT]
    if TARGET_STATION not in stations:
        raise EvaluationError(
            f"Required target station {TARGET_STATION} is missing."
        )

    print(f"Loaded {len(data):,} rows for {len(stations)} evaluation stations.")
    return data, stations


def check_backend():
    print(f"Checking backend at {API_URL}...")
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
    except requests.RequestException as exc:
        raise EvaluationError(
            f"Backend is not reachable at {API_URL}. Start the API first."
        ) from exc
    if response.status_code != 200:
        raise EvaluationError(
            f"Backend health check failed: {response.status_code} {response.text}"
        )
    print("Backend: OK")


def build_snapshot(data, stations, timestamp):
    rows = data[
        (data["timestamp"] == timestamp)
        & data["station_id"].isin(stations)
    ].copy()
    rows = rows.drop_duplicates(subset=["station_id"], keep="first")
    rows = rows.set_index("station_id")
    missing = [station for station in stations if station not in rows.index]
    if missing:
        raise EvaluationError(
            f"Timestamp {timestamp} is missing stations: {missing}"
        )
    return rows.loc[stations]


def find_previous_common_timestamp(data, stations):
    candidates = sorted(
        data[data["timestamp"] < EVALUATION_START]["timestamp"].unique()
    )
    for candidate in reversed(candidates):
        try:
            return pd.Timestamp(candidate), build_snapshot(
                data, stations, pd.Timestamp(candidate)
            )
        except EvaluationError:
            continue
    raise EvaluationError(
        f"No complete historical timestamp precedes {EVALUATION_START}."
    )


def find_evaluation_timestamps(data, stations, count):
    candidates = sorted(
        data[data["timestamp"] >= EVALUATION_START]["timestamp"].unique()
    )
    complete = []
    for candidate in candidates:
        timestamp = pd.Timestamp(candidate)
        try:
            build_snapshot(data, stations, timestamp)
        except EvaluationError:
            continue
        if complete:
            delta = (timestamp - complete[-1]).total_seconds() / 60
            if delta != INTERVAL_MINUTES:
                if len(complete) >= count:
                    break
                complete = []
                continue
        complete.append(timestamp)
        if len(complete) >= count:
            return complete
    raise EvaluationError(
        f"Could not find {count} consecutive complete timestamps from "
        f"{EVALUATION_START}."
    )


def numeric_value(row, field):
    value = row[field]
    if pd.isna(value):
        return None
    return float(value)


def clean_values(row):
    return {
        "temperature_c": numeric_value(row, "temperature_c"),
        "relative_humidity_pct": numeric_value(row, "relative_humidity_pct"),
        "pressure_hpa": numeric_value(row, "pressure_hpa"),
    }


def shifted_values(values, temperature=0.0, humidity=0.0, pressure=0.0):
    result = values.copy()
    if result["temperature_c"] is not None:
        result["temperature_c"] += temperature
    if result["relative_humidity_pct"] is not None:
        result["relative_humidity_pct"] += humidity
    if result["pressure_hpa"] is not None:
        result["pressure_hpa"] += pressure
    return result


def send_batch(stations, timestamp, snapshot, modifier=None):
    readings = []
    for station in stations:
        values = clean_values(snapshot.loc[station])
        if modifier is not None:
            values = modifier(station, values)
        readings.append({
            "station_id": station,
            "timestamp": timestamp.isoformat(),
            **values,
        })

    try:
        response = requests.post(
            f"{API_URL}/ingest/batch",
            json={"readings": readings},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise EvaluationError(f"Batch request failed: {exc}") from exc

    if response.status_code != 200:
        raise EvaluationError(
            f"/ingest/batch failed: {response.status_code} {response.text}"
        )
    payload = response.json()
    if payload.get("error"):
        raise EvaluationError(f"/ingest/batch returned error: {payload['error']}")
    if payload.get("stations_processed") != len(stations):
        raise EvaluationError(
            "Batch did not process all stations: "
            f"{payload.get('stations_processed')}/{len(stations)}"
        )
    results = payload.get("results", [])
    if len(results) != len(stations):
        raise EvaluationError(
            f"Batch returned {len(results)} results for {len(stations)} stations."
        )
    return results


def result_map(results):
    return {str(result.get("station_id")): result for result in results}


def prediction_is_anomaly(result):
    return bool(result.get("anomaly") is True or result.get("anomaly") == 1)


def predicted_cause(result):
    value = result.get("weather_or_sensor")
    return str(value).strip().lower() if value is not None else ""


def zero_safe(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def binary_metrics(observations):
    tp = sum(item["ground_truth"] and item["predicted_anomaly"] for item in observations)
    tn = sum(not item["ground_truth"] and not item["predicted_anomaly"] for item in observations)
    fp = sum(not item["ground_truth"] and item["predicted_anomaly"] for item in observations)
    fn = sum(item["ground_truth"] and not item["predicted_anomaly"] for item in observations)
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": zero_safe(tp + tn, tp + tn + fp + fn),
        "precision": zero_safe(tp, tp + fp),
        "recall": zero_safe(tp, tp + fn),
        "f1": zero_safe(2 * tp, 2 * tp + fp + fn),
        "fpr": zero_safe(fp, fp + tn),
        "fnr": zero_safe(fn, fn + tp),
    }


def cause_attribution(observations):
    weather_correct = 0
    sensor_correct = 0
    cause_incorrect = 0
    cause_unavailable = 0
    for item in observations:
        if not item["ground_truth"]:
            continue
        prediction = item["predicted_anomaly_result"]
        cause = predicted_cause(prediction)
        expected = item["expected_cause"]
        if not item["predicted_anomaly"] or cause not in {"weather", "sensor"}:
            cause_unavailable += 1
        elif expected == "weather" and cause == "weather":
            weather_correct += 1
        elif expected in {"sensor", "sensor/data quality"} and cause == "sensor":
            sensor_correct += 1
        else:
            cause_incorrect += 1
    return {
        "weather_correct": weather_correct,
        "sensor_correct": sensor_correct,
        "cause_incorrect": cause_incorrect,
        "cause_unavailable_non_anomalous": cause_unavailable,
    }


def latency_report(observations, injection_start):
    if injection_start is None:
        return {
            "injection_start_timestamp": None,
            "first_detection_timestamp": None,
            "detection_latency_minutes": None,
        }
    detections = [
        item["timestamp"]
        for item in observations
        if item["timestamp"] >= injection_start and item["predicted_anomaly"]
    ]
    first_detection = min(detections) if detections else None
    latency = (
        (first_detection - injection_start).total_seconds() / 60
        if first_detection is not None
        else None
    )
    return {
        "injection_start_timestamp": injection_start.isoformat(),
        "first_detection_timestamp": (
            first_detection.isoformat() if first_detection is not None else None
        ),
        "detection_latency_minutes": latency,
    }


def observation_record(timestamp, station, result, ground_truth, expected_cause, injection):
    return {
        "timestamp": timestamp,
        "station_id": station,
        "ground_truth": ground_truth,
        "expected_cause": expected_cause,
        "predicted_anomaly": prediction_is_anomaly(result),
        "predicted_cause": predicted_cause(result) or None,
        "predicted_anomaly_result": result,
        "injection": injection,
    }


def serialize_observation(item):
    result = dict(item)
    result["timestamp"] = result["timestamp"].isoformat()
    result.pop("predicted_anomaly_result", None)
    return result


def run_scenario(name, data, stations, timestamps, injection_plan, expected_cause, latency_start=None):
    print(f"Running scenario: {name}")
    reset_live_data()
    time.sleep(REQUEST_DELAY_SECONDS)

    previous_timestamp, previous_snapshot = find_previous_common_timestamp(data, stations)
    send_batch(stations, previous_timestamp, previous_snapshot)

    observations = []
    for step in injection_plan:
        timestamp = step["timestamp"]
        snapshot = build_snapshot(data, stations, timestamp)
        results = send_batch(stations, timestamp, snapshot, step.get("modifier"))
        results_by_station = result_map(results)
        for station in stations:
            ground_truth, cause, injection = step["labels"].get(
                station, (False, None, {"type": "none"})
            )
            result = results_by_station[station]
            observations.append(
                observation_record(
                    timestamp,
                    station,
                    result,
                    ground_truth,
                    cause,
                    injection,
                )
            )
        time.sleep(REQUEST_DELAY_SECONDS)

    metrics = binary_metrics(observations)
    attribution = cause_attribution(observations)
    latency = latency_report(observations, latency_start)
    scenario = {
        "name": name,
        "ground_truth": "evaluator-controlled injection labels",
        "injection": [step["description"] for step in injection_plan],
        "metrics": metrics,
        "cause_attribution": attribution,
        "latency": latency,
        "observations": [serialize_observation(item) for item in observations],
    }
    print(
        f"  TP={metrics['tp']} TN={metrics['tn']} FP={metrics['fp']} "
        f"FN={metrics['fn']} F1={metrics['f1']:.4f}"
    )
    return scenario


def labels_for(stations, anomaly_stations, cause, injection):
    return {
        station: (
            station in anomaly_stations,
            cause if station in anomaly_stations else None,
            injection if station in anomaly_stations else {"type": "none"},
        )
        for station in stations
    }


def make_plan(data, stations, timestamps, scenario):
    if scenario == "NORMAL":
        timestamp = timestamps[0]
        return [{
            "timestamp": timestamp,
            "description": "No modification; normal ground truth.",
            "labels": labels_for(stations, set(), None, {"type": "none"}),
        }]

    if scenario == "REGIONAL WEATHER":
        timestamp = timestamps[0]
        return [{
            "timestamp": timestamp,
            "description": "All stations: temperature +6 C, humidity -10 points, pressure -5 hPa.",
            "modifier": lambda station, values: shifted_values(
                values, temperature=6.0, humidity=-10.0, pressure=-5.0
            ),
            "labels": labels_for(
                stations,
                set(stations),
                "weather",
                {"type": "regional_weather", "temperature_delta_c": 6.0, "humidity_delta_pct": -10.0, "pressure_delta_hpa": -5.0},
            ),
        }]

    if scenario == "ISOLATED SENSOR SPIKE":
        timestamp = timestamps[0]
        return [{
            "timestamp": timestamp,
            "description": "AWS_AP08 temperature +15 C at one timestamp.",
            "modifier": lambda station, values: shifted_values(
                values, temperature=15.0
            ) if station == TARGET_STATION else values,
            "labels": labels_for(
                stations,
                {TARGET_STATION},
                "sensor",
                {"type": "isolated_sensor_spike", "station_id": TARGET_STATION, "temperature_delta_c": 15.0},
            ),
        }]

    if scenario == "PROGRESSIVE SENSOR DRIFT":
        plan = []
        for index, timestamp in enumerate(timestamps[:6]):
            drift = 0.0 if index == 0 else float(index)
            plan.append({
                "timestamp": timestamp,
                "description": (
                    "Clean context observation."
                    if index == 0
                    else f"AWS_AP08 temperature +{drift:.0f} C at drift step {index}."
                ),
                "modifier": (
                    lambda station, values, drift=drift: shifted_values(
                        values, temperature=drift
                    ) if station == TARGET_STATION else values
                ),
                "labels": labels_for(
                    stations,
                    {TARGET_STATION} if index > 0 else set(),
                    "sensor",
                    {"type": "progressive_sensor_drift", "station_id": TARGET_STATION, "temperature_delta_c": drift},
                ),
            })
        return plan

    if scenario == "FROZEN SENSOR":
        frozen_snapshot = build_snapshot(data, stations, timestamps[0])
        frozen_values = clean_values(frozen_snapshot.loc[TARGET_STATION])
        plan = []
        for index, timestamp in enumerate(timestamps[:9]):
            plan.append({
                "timestamp": timestamp,
                "description": (
                    "Clean context observation."
                    if index == 0
                    else "AWS_AP08 repeats its previous clean T/RH/Pressure values while the network advances."
                ),
                "modifier": (
                    lambda station, values: frozen_values.copy()
                    if station == TARGET_STATION else values
                ) if index > 0 else None,
                "labels": labels_for(
                    stations,
                    {TARGET_STATION} if index >= 2 else set(),
                    "sensor",
                    {"type": "frozen_sensor", "station_id": TARGET_STATION, "detectable_from_step": 2},
                ),
            })
        return plan

    if scenario == "MISSING TELEMETRY":
        timestamp = timestamps[0]
        return [{
            "timestamp": timestamp,
            "description": "AWS_AP08 temperature, humidity, and pressure set to null.",
            "modifier": lambda station, values: {
                "temperature_c": None,
                "relative_humidity_pct": None,
                "pressure_hpa": None,
            } if station == TARGET_STATION else values,
            "labels": labels_for(
                stations,
                {TARGET_STATION},
                "sensor/data quality",
                {"type": "missing_telemetry", "station_id": TARGET_STATION},
            ),
        }]

    raise EvaluationError(f"Unknown scenario: {scenario}")


def aggregate_scenarios(scenarios):
    observations = [
        item
        for scenario in scenarios
        for item in scenario["observations"]
    ]
    return {
        "metrics": binary_metrics(observations),
        "cause_attribution": {
            key: sum(scenario["cause_attribution"][key] for scenario in scenarios)
            for key in (
                "weather_correct",
                "sensor_correct",
                "cause_incorrect",
                "cause_unavailable_non_anomalous",
            )
        },
    }


def print_summary(scenarios, overall):
    print("\nFINAL SUMMARY")
    print("Scenario                         TP TN FP FN       F1")
    print("--------------------------------------------------------")
    for scenario in scenarios:
        metrics = scenario["metrics"]
        print(
            f"{scenario['name']:<32} {metrics['tp']:>2} {metrics['tn']:>2} "
            f"{metrics['fp']:>2} {metrics['fn']:>2} {metrics['f1']:.4f}"
        )
    metrics = overall["metrics"]
    print("--------------------------------------------------------")
    print(
        f"{'OVERALL':<32} {metrics['tp']:>2} {metrics['tn']:>2} "
        f"{metrics['fp']:>2} {metrics['fn']:>2} {metrics['f1']:.4f}"
    )
    print(f"Report written to: {REPORT_PATH}")


def main():
    check_backend()
    data, stations = load_dataset()
    previous_timestamp, _ = find_previous_common_timestamp(data, stations)
    print(f"Preceding complete context timestamp: {previous_timestamp}")

    # Reserve enough consecutive timestamps for the longest temporal scenarios.
    timestamps = find_evaluation_timestamps(data, stations, 9)
    scenario_names = [
        "NORMAL",
        "REGIONAL WEATHER",
        "ISOLATED SENSOR SPIKE",
        "PROGRESSIVE SENSOR DRIFT",
        "FROZEN SENSOR",
        "MISSING TELEMETRY",
    ]
    scenarios = []
    for scenario_name in scenario_names:
        plan = make_plan(data, stations, timestamps, scenario_name)
        latency_start = (
            plan[1]["timestamp"]
            if scenario_name == "PROGRESSIVE SENSOR DRIFT"
            else plan[2]["timestamp"]
            if scenario_name == "FROZEN SENSOR"
            else None
        )
        scenarios.append(
            run_scenario(
                scenario_name,
                data,
                stations,
                timestamps,
                plan,
                "sensor" if "SENSOR" in scenario_name else "weather",
                latency_start,
            )
        )

    overall = aggregate_scenarios(scenarios)
    report = {
        "dataset_provenance": (
            "Dataset provenance: synthetic AWS telemetry generated using "
            "LLM-assisted data generation."
        ),
        "evaluation_method": (
            "Evaluation method: controlled anomaly injection into clean "
            "benchmark telemetry followed by inference through the "
            "production /ingest/batch pipeline."
        ),
        "ground_truth_source": "Ground truth source: evaluator-controlled injection labels.",
        "metric_note": "These controlled benchmark metrics are not real-world accuracy.",
        "api_url": API_URL,
        "dataset_path": str(DATASET_PATH),
        "evaluation_start": EVALUATION_START.isoformat(),
        "preceding_context_timestamp": previous_timestamp.isoformat(),
        "stations": stations,
        "scenarios": scenarios,
        "overall": overall,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_summary(scenarios, overall)


if __name__ == "__main__":
    try:
        main()
    except EvaluationError as exc:
        print(f"EVALUATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
