import csv
import sys
import time
from pathlib import Path

import requests


BASE_URL = "http://127.0.0.1:8000"

BACKEND_DIR = Path(__file__).resolve().parent

FIXTURE_PATH = (
    BACKEND_DIR / "SIH26073_AP_AWS_observations.csv"
)

SCENARIO_IDS = {
    "spike": "scen-temp-spike",
    "drop": "scen-temp-drop",
    "jump": "scen-pressure-jump",
    "heatwave": "scen-regional-heatwave",
    "cold_spell": "scen-regional-cold-spell",
}

EXPECTED_CLASS = {
    "spike": "sensor",
    "drop": "sensor",
    "jump": "sensor",
    "heatwave": "weather",
    "cold_spell": "weather",
}

REQUIRED_EVIDENCE = [
    "temporal",
    "spatial",
    "multivariate",
    "data_quality",
    "frozen_sensor",
    "drift",
    "progressive_drift",
    "directional_consistency",
    "persistence",
    "cumulative_abnormality",
    "regional_event",
    "network_coherence",
    "isolation",
    "sensor_fault",
    "evidence_anomaly_score",
    "network_station_count",
]


def main():

    print("=" * 90)
    print("SKYGUARDAI — 100-CASE SIMULATOR ACCEPTANCE TEST")
    print("=" * 90)

    if not FIXTURE_PATH.exists():
        print(f"\nERROR: Fixture not found:")
        print(FIXTURE_PATH)
        sys.exit(1)

    with open(
        FIXTURE_PATH,
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    print(f"\nFixture rows: {len(rows)}")

    if len(rows) != 100:
        print("ERROR: Expected exactly 100 fixture rows.")
        sys.exit(1)

    counts = {}

    for row in rows:
        scenario = row["anomaly_type"]
        counts[scenario] = counts.get(scenario, 0) + 1

    print("\nFixture distribution:")
    for scenario in sorted(counts):
        print(f"  {scenario:12s}: {counts[scenario]:2d}")

    print("\nStarting API acceptance test...")
    print(f"Backend: {BASE_URL}")
    print("-" * 90)

    passed = 0
    failed = 0

    classification_counts = {}

    failures = []

    session = requests.Session()

    for index, row in enumerate(rows, start=1):

        scenario = row["anomaly_type"]
        station = row["station_id"]

        scenario_id = SCENARIO_IDS.get(scenario)

        if scenario_id is None:
            failed += 1
            failures.append(
                f"{index}: unknown scenario {scenario}"
            )
            continue

        payload = {
            "station_id": station,
            "scenario_id": scenario_id,
            "intensity": 85,
        }

        start = time.perf_counter()

        try:
            response = session.post(
                f"{BASE_URL}/simulate",
                json=payload,
                timeout=60,
            )

            elapsed = time.perf_counter() - start

            if response.status_code != 200:
                failed += 1
                failures.append(
                    f"{index}: {station}/{scenario} "
                    f"HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

                print(
                    f"[FAIL] {index:03d}/100 "
                    f"{station:8s} {scenario:12s} "
                    f"HTTP {response.status_code}"
                )

                continue

            result = response.json()

            problems = []

            # -------------------------------------------------
            # Basic response validation
            # -------------------------------------------------

            if result.get("station_id") != station:
                problems.append(
                    f"station_id={result.get('station_id')}"
                )

            if result.get("features_computed_count") != 50:
                problems.append(
                    "features_computed_count != 50"
                )

            # -------------------------------------------------
            # Network context validation
            # -------------------------------------------------

            evidence = result.get("evidence") or {}

            network_count = evidence.get(
                "network_station_count"
            )

            if network_count != 20:
                problems.append(
                    f"network_station_count={network_count}"
                )

            # -------------------------------------------------
            # Evidence validation
            # -------------------------------------------------

            missing_evidence = [
                key
                for key in REQUIRED_EVIDENCE
                if key not in evidence
            ]

            if missing_evidence:
                problems.append(
                    "missing evidence: "
                    + ",".join(missing_evidence)
                )

            # -------------------------------------------------
            # Classification validation
            # -------------------------------------------------

            actual_class = result.get(
                "weather_or_sensor"
            )

            expected_class = EXPECTED_CLASS[scenario]

            classification_counts[
                (scenario, actual_class)
            ] = classification_counts.get(
                (scenario, actual_class),
                0,
            ) + 1

            if actual_class != expected_class:
                problems.append(
                    f"classification={actual_class}, "
                    f"expected={expected_class}"
                )

            # -------------------------------------------------
            # Anomaly validation
            # -------------------------------------------------

            if result.get("anomaly") is not True:
                problems.append(
                    "anomaly != True"
                )

            if result.get("confidence") is None:
                problems.append(
                    "confidence is None"
                )

            # -------------------------------------------------
            # Result
            # -------------------------------------------------

            if problems:

                failed += 1

                failure_text = (
                    f"{index}: {station}/{scenario}: "
                    + " | ".join(problems)
                )

                failures.append(failure_text)

                print(
                    f"[FAIL] {index:03d}/100 "
                    f"{station:8s} {scenario:12s} "
                    f"{actual_class or 'none':7s} "
                    f"{elapsed:6.2f}s"
                )

            else:

                passed += 1

                print(
                    f"[PASS] {index:03d}/100 "
                    f"{station:8s} {scenario:12s} "
                    f"{actual_class:7s} "
                    f"{elapsed:6.2f}s"
                )

        except Exception as exc:

            failed += 1

            failures.append(
                f"{index}: {station}/{scenario}: "
                f"{type(exc).__name__}: {exc}"
            )

            print(
                f"[FAIL] {index:03d}/100 "
                f"{station:8s} {scenario:12s} "
                f"ERROR: {exc}"
            )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print("\n" + "=" * 90)
    print("SIMULATOR ACCEPTANCE RESULT")
    print("=" * 90)

    print(f"\nPassed : {passed}/100")
    print(f"Failed : {failed}/100")

    print("\nCLASSIFICATION RESULTS")
    print("-" * 90)

    for scenario in [
        "cold_spell",
        "drop",
        "heatwave",
        "jump",
        "spike",
    ]:

        scenario_total = sum(
            count
            for (s, _), count
            in classification_counts.items()
            if s == scenario
        )

        print(f"\n{scenario}: {scenario_total}/20")

        for (s, classification), count in sorted(
            classification_counts.items()
        ):

            if s == scenario:
                print(
                    f"  {classification}: {count}"
                )

    if failures:

        print("\nFAILURES")
        print("-" * 90)

        for failure in failures:
            print(f"  {failure}")

    print("\n" + "=" * 90)

    if failed == 0:

        print("100/100 SIMULATOR ACCEPTANCE TEST PASSED")
        print("=" * 90)
        sys.exit(0)

    else:

        print("SIMULATOR ACCEPTANCE TEST FAILED")
        print("=" * 90)
        sys.exit(1)


if __name__ == "__main__":
    main()