import pandas as pd
import numpy as np

from feature_engineering import build_features, FEATURE_COLS


DATASET_PATH = r"C:\Users\dilee\Desktop\Null_Deviants\ML training\SIH26073_AP_AWS_observations.csv"

STATION_ID = "AWS_AP01"
TARGET_TIMESTAMP = "2025-01-02 12:00:00"

TOLERANCE = 1e-3


def main():
    print("=" * 70)
    print("SIH26073 FEATURE ENGINEERING VALIDATION")
    print("=" * 70)

    print("\nLoading dataset...")
    df = pd.read_csv(DATASET_PATH)

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print(f"Dataset rows: {len(df):,}")
    print(f"Dataset columns: {len(df.columns)}")

    # ---------------------------------------------------------
    # 1. Select target observation
    # ---------------------------------------------------------

    target_rows = df[
        (df["station_id"] == STATION_ID)
        & (df["timestamp"] == TARGET_TIMESTAMP)
    ]

    if target_rows.empty:
        raise ValueError(
            f"Could not find target row: {STATION_ID} @ {TARGET_TIMESTAMP}"
        )

    target = target_rows.iloc[0]

    print("\nTarget observation:")
    print(f"  Station:   {target['station_id']}")
    print(f"  Timestamp: {target['timestamp']}")
    print(f"  T:         {target['temperature_c']}")
    print(f"  RH:        {target['relative_humidity_pct']}")
    print(f"  Pressure:  {target['pressure_hpa']}")

    # ---------------------------------------------------------
    # 2. Build same-station history
    # ---------------------------------------------------------

    history = df[
        (df["station_id"] == STATION_ID)
        & (df["timestamp"] < target["timestamp"])
    ].sort_values("timestamp").tail(96)

    history = history[
        [
            "timestamp",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ]
    ].copy()

    print(f"\nSame-station history rows: {len(history)}")

    # ---------------------------------------------------------
    # 3. Build all-station context at target timestamp
    # ---------------------------------------------------------

    all_station_history = df[
        df["timestamp"] == target["timestamp"]
    ][
        [
            "station_id",
            "timestamp",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ]
    ].copy()

    print(
        f"Stations available at target timestamp: "
        f"{len(all_station_history)}"
    )

    # ---------------------------------------------------------
    # 4. Generate our features
    # ---------------------------------------------------------

    generated = build_features(
        station_id=target["station_id"],
        timestamp=target["timestamp"],
        temperature_c=target["temperature_c"],
        relative_humidity_pct=target["relative_humidity_pct"],
        pressure_hpa=target["pressure_hpa"],
        history=history,
        all_station_history=all_station_history,
    )

    print(f"\nFeatures generated: {len(generated)}")

    # ---------------------------------------------------------
    # 5. Validate exact feature count
    # ---------------------------------------------------------

    if len(generated) != 50:
        raise ValueError(
            f"Expected 50 generated features, got {len(generated)}"
        )

    missing_generated = [
        feature
        for feature in FEATURE_COLS
        if feature not in generated
    ]

    if missing_generated:
        raise ValueError(
            "Generated features missing:\n"
            + "\n".join(missing_generated)
        )

    # ---------------------------------------------------------
    # 6. Compare features that exist directly in dataset
    # ---------------------------------------------------------

    # These five are created by train_model_v2.py and therefore
    # are not stored in the CSV.
    derived_during_training = {
        "timestamp_gap_seconds",
        "timestamp_gap_flag",
        "temperature_dev_24h",
        "humidity_dev_24h",
        "pressure_dev_24h",
    }

    comparable_features = [
        feature
        for feature in FEATURE_COLS
        if feature in df.columns
        and feature not in derived_during_training
    ]

    print(
        f"Dataset-stored model features compared: "
        f"{len(comparable_features)}"
    )

    matches = []
    mismatches = []
    skipped_nan = []

    for feature in comparable_features:
        dataset_value = target[feature]
        generated_value = generated[feature]

        if pd.isna(dataset_value) or pd.isna(generated_value):
            skipped_nan.append(
                (
                    feature,
                    dataset_value,
                    generated_value,
                )
            )
            continue

        try:
            dataset_value = float(dataset_value)
            generated_value = float(generated_value)
        except (TypeError, ValueError):
            skipped_nan.append(
                (
                    feature,
                    dataset_value,
                    generated_value,
                )
            )
            continue

        difference = abs(dataset_value - generated_value)

        if np.isclose(
            dataset_value,
            generated_value,
            rtol=TOLERANCE,
            atol=TOLERANCE,
        ):
            matches.append(
                (
                    feature,
                    dataset_value,
                    generated_value,
                    difference,
                )
            )
        else:
            mismatches.append(
                (
                    feature,
                    dataset_value,
                    generated_value,
                    difference,
                )
            )

    # ---------------------------------------------------------
    # 7. Reconstruct the five training-time features
    # ---------------------------------------------------------

    print("\nReconstructing training-time derived features...")

    # Timestamp gap
    if len(history) > 0:
        previous_timestamp = pd.to_datetime(
            history.iloc[-1]["timestamp"]
        )

        timestamp_gap_seconds = (
            target["timestamp"] - previous_timestamp
        ).total_seconds()

        timestamp_gap_flag = (
            1.0 if timestamp_gap_seconds != 900 else 0.0
        )
    else:
        timestamp_gap_seconds = -999.0
        timestamp_gap_flag = 1.0

    # 24-hour deviations
    history_24h = history[
        history["timestamp"]
        <= target["timestamp"] - pd.Timedelta(hours=24)
    ]

    # Prefer exact 24-hour observation if available.
    target_24h_timestamp = (
        target["timestamp"] - pd.Timedelta(hours=24)
    )

    exact_24h = history[
        history["timestamp"] == target_24h_timestamp
    ]

    if not exact_24h.empty:
        row_24h = exact_24h.iloc[-1]

        temperature_dev_24h = (
            target["temperature_c"]
            - row_24h["temperature_c"]
        )

        humidity_dev_24h = (
            target["relative_humidity_pct"]
            - row_24h["relative_humidity_pct"]
        )

        pressure_dev_24h = (
            target["pressure_hpa"]
            - row_24h["pressure_hpa"]
        )

    else:
        temperature_dev_24h = -999.0
        humidity_dev_24h = -999.0
        pressure_dev_24h = -999.0

    derived_features = {
        "timestamp_gap_seconds": timestamp_gap_seconds,
        "timestamp_gap_flag": timestamp_gap_flag,
        "temperature_dev_24h": temperature_dev_24h,
        "humidity_dev_24h": humidity_dev_24h,
        "pressure_dev_24h": pressure_dev_24h,
    }

    print("\nDerived feature values:")
    for feature, value in derived_features.items():
        print(f"  {feature}: {value}")

    # ---------------------------------------------------------
    # 8. Final summary
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("VALIDATION RESULT")
    print("=" * 70)

    print(f"Expected model features : {len(FEATURE_COLS)}")
    print(f"Generated model features: {len(generated)}")
    print(f"Comparable dataset feats: {len(comparable_features)}")
    print(f"Exact/close matches     : {len(matches)}")
    print(f"Mismatches              : {len(mismatches)}")
    print(f"Skipped due to NaN      : {len(skipped_nan)}")

    if mismatches:
        print("\nMISMATCHES:")
        for feature, dataset_value, generated_value, difference in mismatches:
            print(
                f"  {feature}"
                f"\n    dataset : {dataset_value}"
                f"\n    ours    : {generated_value}"
                f"\n    diff    : {difference}"
            )

    if skipped_nan:
        print("\nSKIPPED NaN FEATURES:")
        for feature, dataset_value, generated_value in skipped_nan:
            print(
                f"  {feature}"
                f" | dataset={dataset_value}"
                f" | ours={generated_value}"
            )

    print("\nDERIVED FEATURE CHECK:")
    print("  These five features are generated during training/runtime")
    print("  and are therefore not directly stored in the CSV.")

    print("\n" + "=" * 70)

    if mismatches:
        print("STATUS: NEEDS CORRECTION")
    else:
        print("STATUS: DATASET-STORED FEATURES MATCH")
    print("=" * 70)


if __name__ == "__main__":
    main()