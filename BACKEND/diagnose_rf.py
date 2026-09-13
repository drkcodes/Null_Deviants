from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

MODEL_PATH = (
    Path(__file__).resolve().parent
    / "model_anomaly_detector.pkl"
)


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


def main():

    print("=" * 70)
    print("SIH26073 — RANDOM FOREST DIAGNOSTIC")
    print("=" * 70)

    print()
    print("Loading model...")
    print(MODEL_PATH)

    model = joblib.load(MODEL_PATH)

    print(
        f"Model type: {type(model).__name__}"
    )

    print(
        f"Model features: "
        f"{len(model.feature_names_in_)}"
    )

    if list(model.feature_names_in_) != FEATURE_COLS:

        print()
        print(
            "ERROR: Model feature order does not "
            "match the expected 50 features."
        )

        print()
        print("Model features:")
        print(
            list(model.feature_names_in_)
        )

        raise RuntimeError(
            "Feature mismatch."
        )

    print(
        "Feature order: OK"
    )

    print()
    print("Loading dataset...")

    df = pd.read_csv(
        DATASET_PATH
    )

    print(
        f"Dataset rows: {len(df):,}"
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = (
        df.sort_values(
            [
                "station_id",
                "timestamp",
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Recreate the two groups of inference-time features
    # that are not stored directly in the dataset.
    # --------------------------------------------------------

    print()
    print(
        "Recreating inference-time features..."
    )

    df["timestamp_gap_seconds"] = (
        df.groupby("station_id")["timestamp"]
        .diff()
        .dt.total_seconds()
    )

    df["timestamp_gap_flag"] = (
        df["timestamp_gap_seconds"] != 900
    ).astype(int)

    df["temperature_dev_24h"] = (
        df["temperature_c"]
        - df["temperature_lag_24h"]
    )

    df["humidity_dev_24h"] = (
        df["relative_humidity_pct"]
        - df["humidity_lag_24h"]
    )

    df["pressure_dev_24h"] = (
        df["pressure_hpa"]
        - df["pressure_lag_24h"]
    )

    # --------------------------------------------------------
    # Use exactly the same missing-value convention as training.
    # --------------------------------------------------------

    X = (
        df[FEATURE_COLS]
        .copy()
        .fillna(-999)
    )

    y = (
        df["anomaly_flag"]
        .astype(int)
    )

    print(
        f"Feature matrix: "
        f"{X.shape[0]:,} rows × "
        f"{X.shape[1]} features"
    )

    # --------------------------------------------------------
    # Overall dataset diagnostic.
    # --------------------------------------------------------

    print()
    print(
        "Running Random Forest..."
    )

    predictions = model.predict(X)

    probabilities = (
        model
        .predict_proba(X)[:, 1]
    )

    print()
    print("=" * 70)
    print("OVERALL MODEL DIAGNOSTIC")
    print("=" * 70)

    print()

    print(
        classification_report(
            y,
            predictions,
            target_names=[
                "Normal",
                "Anomaly",
            ],
            digits=4,
        )
    )

    print(
        "Confusion matrix:"
    )

    print(
        confusion_matrix(
            y,
            predictions,
        )
    )

    # --------------------------------------------------------
    # NORMAL-ONLY diagnostic.
    # --------------------------------------------------------

    normal_mask = (
        y == 0
    )

    normal_predictions = (
        predictions[normal_mask]
    )

    normal_false_alarms = (
        normal_predictions == 1
    ).sum()

    normal_total = (
        normal_mask.sum()
    )

    normal_fpr = (
        normal_false_alarms
        / normal_total
        if normal_total
        else 0
    )

    print()
    print("=" * 70)
    print("NORMAL-ONLY DIAGNOSTIC")
    print("=" * 70)

    print()

    print(
        f"Normal observations: "
        f"{normal_total:,}"
    )

    print(
        f"False alarms: "
        f"{normal_false_alarms:,}"
    )

    print(
        f"False-positive rate: "
        f"{normal_fpr:.4%}"
    )

    # --------------------------------------------------------
    # Check the actual benchmark timestamp used by v3.
    # --------------------------------------------------------

    target_timestamp = pd.Timestamp(
        "2025-12-31 00:00:00"
    )

    target = df[
        df["timestamp"]
        == target_timestamp
    ].copy()

    print()
    print("=" * 70)
    print("TARGET TIMESTAMP CHECK")
    print("=" * 70)

    print()
    print(
        f"Timestamp: {target_timestamp}"
    )

    print(
        f"Rows found: {len(target)}"
    )

    if not target.empty:

        target_X = (
            target[FEATURE_COLS]
            .fillna(-999)
        )

        target_y = (
            target["anomaly_flag"]
            .astype(int)
        )

        target_pred = (
            model.predict(target_X)
        )

        target_proba = (
            model.predict_proba(
                target_X
            )[:, 1]
        )

        for index, (_, row) in enumerate(
            target.iterrows()
        ):

            print(
                f"{row['station_id']}: "
                f"truth="
                f"{target_y.iloc[index]} "
                f"prediction="
                f"{target_pred[index]} "
                f"probability="
                f"{target_proba[index]:.3f}"
            )

    # --------------------------------------------------------
    # Compare model artifact with alternate v2 artifact
    # if it exists.
    # --------------------------------------------------------

    alternate_model_path = (
        Path(__file__).resolve().parent
        / "anomaly_model_v2.pkl"
    )

    if alternate_model_path.exists():

        print()
        print("=" * 70)
        print("ALTERNATE MODEL ARTIFACT CHECK")
        print("=" * 70)

        print()
        print(
            f"Found: {alternate_model_path}"
        )

        alternate = joblib.load(
            alternate_model_path
        )

        alternate_predictions = (
            alternate.predict(X)
        )

        print(
            "Current model anomaly rate: "
            f"{predictions.mean():.4%}"
        )

        print(
            "Alternate v2 model anomaly rate: "
            f"{alternate_predictions.mean():.4%}"
        )

        if hasattr(
            alternate,
            "feature_names_in_",
        ):

            print(
                "Alternate feature count: "
                f"{len(alternate.feature_names_in_)}"
            )

    print()
    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()