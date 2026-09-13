import json
import time
from pathlib import Path
from database import reset_live_data as reset_live_data_db
import pandas as pd
import requests


API_URL = "http://127.0.0.1:8000"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "ML training" / "SIH26073_AP_AWS_observations.csv"

STATION_COUNT = 20
BASE_TIMESTAMP = "2025-12-31T00:00:00+05:30"
TEST_TIMESTAMP = "2025-12-31T00:15:00+05:30"

REQUEST_DELAY = 0.05


def load_dataset():
    print("Loading benchmark dataset...")

    df = pd.read_csv(DATASET_PATH)

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = df.sort_values(["timestamp", "station_id"]).reset_index(drop=True)

    stations = sorted(df["station_id"].unique())

    if len(stations) < STATION_COUNT:
        raise RuntimeError(
            f"Expected at least {STATION_COUNT} stations, found {len(stations)}"
        )

    stations = stations[:STATION_COUNT]

    # Use the final clean benchmark observation before the evaluation window.
    cutoff = pd.Timestamp("2025-12-31 00:00:00")

    baseline = (
        df[
            (df["timestamp"] < cutoff)
            & (df["station_id"].isin(stations))
            & (df["anomaly_flag"] == False)
        ]
        .sort_values("timestamp")
        .groupby("station_id")
        .tail(1)
    )

    baseline = baseline.set_index("station_id")

    missing = [s for s in stations if s not in baseline.index]

    if missing:
        raise RuntimeError(
            f"Could not find clean baseline observations for: {missing}"
        )

    print(f"Dataset loaded: {len(df):,} rows")
    print(f"Evaluation stations: {len(stations)}")

    return df, stations, baseline


def reset_live_data():
    reset_live_data_db()


def ingest(
    station_id,
    timestamp,
    temperature_c,
    relative_humidity_pct,
    pressure_hpa,
):
    payload = {
        "station_id": station_id,
        "timestamp": timestamp,
        "temperature_c": temperature_c,
        "relative_humidity_pct": relative_humidity_pct,
        "pressure_hpa": pressure_hpa,
    }

    response = requests.post(
        f"{API_URL}/ingest",
        json=payload,
        timeout=15,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"/ingest failed: {response.status_code} {response.text}"
        )

    return response.json()


def row_payload(row, timestamp):
    return {
        "station_id": row.name,
        "timestamp": timestamp,
        "temperature_c": float(row["temperature_c"]),
        "relative_humidity_pct": float(row["relative_humidity_pct"]),
        "pressure_hpa": float(row["pressure_hpa"]),
    }


def ingest_baseline(stations, baseline):
    results = []

    for station in stations:
        row = baseline.loc[station]

        result = ingest(
            station_id=station,
            timestamp=BASE_TIMESTAMP,
            temperature_c=float(row["temperature_c"]),
            relative_humidity_pct=float(row["relative_humidity_pct"]),
            pressure_hpa=float(row["pressure_hpa"]),
        )

        results.append(result)

        time.sleep(REQUEST_DELAY)

    return results


def run_scenario(
    name,
    expected_anomaly,
    expected_classification,
    modifier,
    stations,
    baseline,
):
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    # Completely independent scenario.
    reset_live_data()

    # Establish a clean previous observation for every station.
    ingest_baseline(stations, baseline)

    results = []

    for station in stations:
        row = baseline.loc[station]

        values = {
            "temperature_c": float(row["temperature_c"]),
            "relative_humidity_pct": float(row["relative_humidity_pct"]),
            "pressure_hpa": float(row["pressure_hpa"]),
        }

        values = modifier(station, values)

        result = ingest(
            station_id=station,
            timestamp=TEST_TIMESTAMP,
            temperature_c=values["temperature_c"],
            relative_humidity_pct=values["relative_humidity_pct"],
            pressure_hpa=values["pressure_hpa"],
        )

        results.append(
            {
                "station_id": station,
                "result": result,
            }
        )

        time.sleep(REQUEST_DELAY)

    anomaly_results = [
        item
        for item in results
        if item["result"].get("anomaly") is True
    ]

    weather_results = [
        item
        for item in anomaly_results
        if item["result"].get("weather_or_sensor") == "weather"
    ]

    sensor_results = [
        item
        for item in anomaly_results
        if item["result"].get("weather_or_sensor") == "sensor"
    ]

    if expected_classification is None:
        passed = (
            len(anomaly_results) == 0
            if expected_anomaly is False
            else len(anomaly_results) > 0
        )

    elif expected_classification == "weather":
        passed = (
            len(anomaly_results) > 0
            and len(weather_results) > 0
        )

    elif expected_classification == "sensor":
        passed = (
            len(anomaly_results) > 0
            and len(sensor_results) > 0
        )

    else:
        passed = False

    print(f"Expected anomaly       : {expected_anomaly}")
    print(f"Expected classification: {expected_classification}")
    print(f"Anomalies detected     : {len(anomaly_results)}/{len(results)}")
    print(f"Weather classifications : {len(weather_results)}")
    print(f"Sensor classifications  : {len(sensor_results)}")

    for item in anomaly_results:
        result = item["result"]

        print(
            f"  {item['station_id']}: "
            f"anomaly={result.get('anomaly')} "
            f"score={result.get('score')} "
            f"class={result.get('weather_or_sensor')} "
            f"confidence={result.get('confidence')}"
        )

    print(f"RESULT: {'PASS' if passed else 'FAIL'}")

    return {
        "name": name,
        "expected_anomaly": expected_anomaly,
        "expected_classification": expected_classification,
        "total": len(results),
        "anomalies": len(anomaly_results),
        "weather": len(weather_results),
        "sensor": len(sensor_results),
        "passed": passed,
        "results": results,
    }


def normal_modifier(station, values):
    return values


def regional_weather_modifier(station, values):
    # Coherent atmospheric event across the entire network.
    values["temperature_c"] += 6.0
    values["relative_humidity_pct"] -= 10.0
    values["pressure_hpa"] -= 5.0

    return values


def isolated_spike_modifier(station, values):
    if station == "AWS_AP08":
        values["temperature_c"] += 15.0

    return values


def drift_modifier_factory(step):
    def modifier(station, values):
        if station == "AWS_AP08":
            values["temperature_c"] += float(step)

        return values

    return modifier


def frozen_modifier(station, values):
    # Repeated identical reading.
    # The baseline timestamp already establishes the previous value.
    return values


def missing_modifier(station, values):
    if station == "AWS_AP08":
        values["temperature_c"] = None
        values["relative_humidity_pct"] = None
        values["pressure_hpa"] = None

    return values


def mixed_discrimination_modifier(station, values):
    # First establish a regional event.
    values["temperature_c"] += 7.0
    values["relative_humidity_pct"] -= 12.0
    values["pressure_hpa"] -= 6.0

    # Then make AP08 substantially different from the regional event.
    if station == "AWS_AP08":
        values["temperature_c"] += 18.0

    return values


def run():
    print()
    print("=" * 70)
    print("SIH26073 — 2G EVALUATION V2")
    print("=" * 70)
    print()
    print("Model: existing Random Forest pipeline")
    print("Inputs: Temperature / Relative Humidity / Pressure / Timestamp")
    print("Database: historical data preserved; live data isolated per test")
    print()

    # Verify backend is reachable.
    try:
        response = requests.get(
            f"{API_URL}/",
            timeout=5,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Backend check failed: "
                f"{response.status_code} {response.text}"
            )

    except requests.RequestException as exc:
        raise RuntimeError(
            "Backend is not reachable. Start it before running this evaluator."
        ) from exc

    _, stations, baseline = load_dataset()

    results = []

    # ------------------------------------------------------------
    # 2G.1 NORMAL TELEMETRY
    # ------------------------------------------------------------
    results.append(
        run_scenario(
            name="2G.1 Normal Telemetry",
            expected_anomaly=False,
            expected_classification=None,
            modifier=normal_modifier,
            stations=stations,
            baseline=baseline,
        )
    )

    # ------------------------------------------------------------
    # 2G.2 REGIONAL WEATHER EVENT
    # ------------------------------------------------------------
    results.append(
        run_scenario(
            name="2G.2 Regional Weather Event",
            expected_anomaly=True,
            expected_classification="weather",
            modifier=regional_weather_modifier,
            stations=stations,
            baseline=baseline,
        )
    )

    # ------------------------------------------------------------
    # 2G.3 ISOLATED SENSOR SPIKE
    # ------------------------------------------------------------
    results.append(
        run_scenario(
            name="2G.3 Isolated Sensor Spike",
            expected_anomaly=True,
            expected_classification="sensor",
            modifier=isolated_spike_modifier,
            stations=stations,
            baseline=baseline,
        )
    )

    # ------------------------------------------------------------
    # 2G.4 GRADUAL SENSOR DRIFT
    # ------------------------------------------------------------
    drift_outputs = []

    reset_live_data()

    ingest_baseline(stations, baseline)

    drift_steps = [1.0, 2.0, 3.0, 4.0, 5.0]

    for step in drift_steps:
        print()
        print(f"2G.4 Drift step: +{step:.1f} °C")

        for station in stations:
            row = baseline.loc[station]

            values = {
                "temperature_c": float(row["temperature_c"]),
                "relative_humidity_pct": float(
                    row["relative_humidity_pct"]
                ),
                "pressure_hpa": float(row["pressure_hpa"]),
            }

            values = drift_modifier_factory(step)(station, values)

            result = ingest(
                station_id=station,
                timestamp=TEST_TIMESTAMP,
                temperature_c=values["temperature_c"],
                relative_humidity_pct=values["relative_humidity_pct"],
                pressure_hpa=values["pressure_hpa"],
            )

            if station == "AWS_AP08":
                drift_outputs.append(result)

            time.sleep(REQUEST_DELAY)

    final_drift = drift_outputs[-1]

    drift_passed = (
        final_drift.get("anomaly") is True
        and final_drift.get("weather_or_sensor") == "sensor"
    )

    print()
    print(f"Expected final classification: sensor")
    print(
        f"Final AP08: anomaly={final_drift.get('anomaly')} "
        f"score={final_drift.get('score')} "
        f"class={final_drift.get('weather_or_sensor')} "
        f"confidence={final_drift.get('confidence')}"
    )
    print(f"RESULT: {'PASS' if drift_passed else 'FAIL'}")

    results.append(
        {
            "name": "2G.4 Gradual Sensor Drift",
            "expected_anomaly": True,
            "expected_classification": "sensor",
            "total": len(drift_outputs),
            "anomalies": sum(
                r.get("anomaly") is True for r in drift_outputs
            ),
            "weather": sum(
                r.get("weather_or_sensor") == "weather"
                for r in drift_outputs
            ),
            "sensor": sum(
                r.get("weather_or_sensor") == "sensor"
                for r in drift_outputs
            ),
            "passed": drift_passed,
            "results": drift_outputs,
        }
    )

    # ------------------------------------------------------------
    # 2G.5 FROZEN SENSOR
    # ------------------------------------------------------------
    frozen_outputs = []

    reset_live_data()

    ingest_baseline(stations, baseline)

    for step in range(8):
        # Move simulated time forward by 15 minutes.
        timestamp = pd.Timestamp(TEST_TIMESTAMP) + pd.Timedelta(
            minutes=15 * step
        )
        timestamp = timestamp.isoformat()

        row = baseline.loc["AWS_AP08"]

        result = ingest(
            station_id="AWS_AP08",
            timestamp=timestamp,
            temperature_c=float(row["temperature_c"]),
            relative_humidity_pct=float(row["relative_humidity_pct"]),
            pressure_hpa=float(row["pressure_hpa"]),
        )

        frozen_outputs.append(result)

        time.sleep(REQUEST_DELAY)

    final_frozen = frozen_outputs[-1]

    frozen_passed = (
        final_frozen.get("anomaly") is True
        and final_frozen.get("weather_or_sensor") == "sensor"
    )

    print()
    print("=" * 70)
    print("2G.5 Frozen Sensor")
    print("=" * 70)

    for index, result in enumerate(frozen_outputs, start=1):
        print(
            f"Step {index}: "
            f"anomaly={result.get('anomaly')} "
            f"score={result.get('score')} "
            f"class={result.get('weather_or_sensor')}"
        )

    print(
        f"Final: anomaly={final_frozen.get('anomaly')} "
        f"class={final_frozen.get('weather_or_sensor')} "
        f"confidence={final_frozen.get('confidence')}"
    )

    print(f"RESULT: {'PASS' if frozen_passed else 'FAIL'}")

    results.append(
        {
            "name": "2G.5 Frozen Sensor",
            "expected_anomaly": True,
            "expected_classification": "sensor",
            "total": len(frozen_outputs),
            "anomalies": sum(
                r.get("anomaly") is True for r in frozen_outputs
            ),
            "weather": sum(
                r.get("weather_or_sensor") == "weather"
                for r in frozen_outputs
            ),
            "sensor": sum(
                r.get("weather_or_sensor") == "sensor"
                for r in frozen_outputs
            ),
            "passed": frozen_passed,
            "results": frozen_outputs,
        }
    )

    # ------------------------------------------------------------
    # 2G.6 MISSING TELEMETRY
    # ------------------------------------------------------------
    results.append(
        run_scenario(
            name="2G.6 Missing Telemetry",
            expected_anomaly=True,
            expected_classification="sensor",
            modifier=missing_modifier,
            stations=stations,
            baseline=baseline,
        )
    )

    # ------------------------------------------------------------
    # 2G.7 REGIONAL VS ISOLATED DISCRIMINATION
    # ------------------------------------------------------------
    results.append(
        run_scenario(
            name="2G.7 Regional vs Isolated Discrimination",
            expected_anomaly=True,
            expected_classification="sensor",
            modifier=mixed_discrimination_modifier,
            stations=stations,
            baseline=baseline,
        )
    )

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------
    print()
    print()
    print("=" * 70)
    print("2G EVALUATION V2 — SUMMARY")
    print("=" * 70)

    passed = sum(result["passed"] for result in results)
    total = len(results)

    print()

    for result in results:
        print(
            f"{result['name']:<42} "
            f"{'PASS' if result['passed'] else 'FAIL'}"
        )

    print()
    print(f"Scenario score: {passed}/{total}")
    print()

    print("Anomaly detections across scenarios:")
    print(
        "  2G.1 normal false alarms: "
        f"{results[0]['anomalies']}"
    )

    print(
        "  2G.2 regional weather anomalies: "
        f"{results[1]['anomalies']}"
    )

    print(
        "  2G.3 isolated sensor anomalies: "
        f"{results[2]['anomalies']}"
    )

    print(
        "  2G.4 drift anomalies: "
        f"{results[3]['anomalies']}"
    )

    print(
        "  2G.5 frozen anomalies: "
        f"{results[4]['anomalies']}"
    )

    print(
        "  2G.6 missing anomalies: "
        f"{results[5]['anomalies']}"
    )

    print(
        "  2G.7 discrimination anomalies: "
        f"{results[6]['anomalies']}"
    )

    report_path = Path(__file__).resolve().parent / "2g_evaluation_v2_report.json"

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, default=str)

    print()
    print(f"Detailed report saved to:")
    print(report_path)

    print()
    print("=" * 70)
    print("Evaluation complete.")
    print("=" * 70)


if __name__ == "__main__":
    run()