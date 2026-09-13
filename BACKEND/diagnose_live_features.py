from __future__ import annotations

"""
SIH26073 — LIVE vs OFFLINE FEATURE DIFFERENTIAL

Purpose:
Compare the 50 features produced by the canonical feature engine when
fed directly from the benchmark CSV versus the same engine fed from the
PostgreSQL history/context used by the live backend.

This script DOES NOT:
- modify the database
- call /ingest
- modify the model
- modify feature_engineering.py

It is intentionally diagnostic only.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make imports work when executed from BACKEND.
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from database import (  # noqa: E402
    get_station_feature_history,
    get_latest_station_context,
)
from feature_engineering import (  # noqa: E402
    FEATURE_COLS,
    build_features,
    build_model_row,
)


DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

STATION_ID = "AWS_AP01"
TARGET_TIMESTAMP = "2025-12-31 00:00:00"

# Floating-point differences below this are treated as equivalent.
ABS_TOL = 1e-9
REL_TOL = 1e-7


def find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    lookup = {str(c).strip().lower(): c for c in df.columns}

    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]

    raise RuntimeError(
        "Could not find any of these columns: "
        + ", ".join(candidates)
        + "\nAvailable columns:\n"
        + ", ".join(map(str, df.columns))
    )


def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    station_col = find_column(
        df,
        ["station_id", "station", "aws_station_id"],
    )
    timestamp_col = find_column(
        df,
        ["timestamp", "datetime", "date_time", "time"],
    )
    temperature_col = find_column(
        df,
        ["temperature_c", "temperature", "temp_c"],
    )
    humidity_col = find_column(
        df,
        [
            "relative_humidity_pct",
            "relative_humidity",
            "humidity_pct",
            "humidity",
        ],
    )
    pressure_col = find_column(
        df,
        [
            "pressure_hpa",
            "atmospheric_pressure_hpa",
            "pressure",
        ],
    )

    result = pd.DataFrame(
        {
            "station_id": df[station_col].astype(str),
            "timestamp": pd.to_datetime(
                df[timestamp_col],
                errors="coerce",
            ),
            "temperature_c": pd.to_numeric(
                df[temperature_col],
                errors="coerce",
            ),
            "relative_humidity_pct": pd.to_numeric(
                df[humidity_col],
                errors="coerce",
            ),
            "pressure_hpa": pd.to_numeric(
                df[pressure_col],
                errors="coerce",
            ),
        }
    )

    result = result.dropna(subset=["timestamp"])
    result = result.sort_values(
        ["station_id", "timestamp"]
    ).reset_index(drop=True)

    return result


def compare_values(offline, live):
    if pd.isna(offline) and pd.isna(live):
        return True, 0.0

    try:
        a = float(offline)
        b = float(live)
    except (TypeError, ValueError):
        return str(offline) == str(live), np.nan

    if not np.isfinite(a) or not np.isfinite(b):
        return a == b, np.nan

    diff = b - a

    equal = np.isclose(
        a,
        b,
        atol=ABS_TOL,
        rtol=REL_TOL,
        equal_nan=True,
    )

    return bool(equal), float(diff)


def print_feature_table(
    offline_features: dict,
    live_features: dict,
) -> int:
    mismatches = []

    print()
    print(
        "FEATURE                         OFFLINE             LIVE"
    )
    print("-" * 78)

    for feature in FEATURE_COLS:
        offline = offline_features.get(feature)
        live = live_features.get(feature)

        equal, diff = compare_values(
            offline,
            live,
        )

        marker = "OK" if equal else "DIFF"

        if not equal:
            mismatches.append(
                (feature, offline, live, diff)
            )

        print(
            f"{feature:<32} "
            f"{str(offline):<19} "
            f"{str(live):<19} "
            f"{marker}"
        )

    print()
    print("=" * 78)
    print(f"Total features : {len(FEATURE_COLS)}")
    print(f"Mismatches     : {len(mismatches)}")

    if mismatches:
        print()
        print("FIRST MEANINGFUL DIFFERENCES")
        print("-" * 78)

        for feature, offline, live, diff in mismatches[:20]:
            print(
                f"{feature:<32} "
                f"offline={offline!r:<18} "
                f"live={live!r:<18} "
                f"diff={diff!r}"
            )

    return len(mismatches)


def main() -> None:
    print("=" * 78)
    print("SIH26073 — LIVE vs OFFLINE FEATURE DIFFERENTIAL")
    print("=" * 78)
    print(f"Dataset : {DATASET_PATH}")
    print(f"Station : {STATION_ID}")
    print(f"Target  : {TARGET_TIMESTAMP}")
    print()

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    raw = pd.read_csv(DATASET_PATH)
    data = normalize_dataset(raw)
    data["timestamp"] = data["timestamp"].dt.tz_localize("Asia/Kolkata")
    target_ts = pd.Timestamp(TARGET_TIMESTAMP).tz_localize("Asia/Kolkata")

    target_rows = data[
        (data["station_id"] == STATION_ID)
        & (data["timestamp"] == target_ts)
    ]

    if target_rows.empty:
        raise RuntimeError(
            f"No dataset observation found for "
            f"{STATION_ID} at {TARGET_TIMESTAMP}"
        )

    target = target_rows.iloc[-1]

    print(
        "RAW TARGET:"
    )
    print(
        f"  T  = {target['temperature_c']}"
    )
    print(
        f"  RH = {target['relative_humidity_pct']}"
    )
    print(
        f"  P  = {target['pressure_hpa']}"
    )

    # ------------------------------------------------------------------
    # OFFLINE / DATASET CONTEXT
    #
    # Exactly the same raw source is used to construct:
    #   - previous station history
    #   - same-timestamp all-station context
    # ------------------------------------------------------------------

    dataset_station = data[
        data["station_id"] == STATION_ID
    ].copy()

    dataset_history = dataset_station[
        dataset_station["timestamp"] < target_ts
    ].tail(96).copy()

    dataset_same_time = data[
        data["timestamp"] == target_ts
    ].copy()

    print()
    print("DATASET CONTEXT:")
    print(f"  station history rows : {len(dataset_history)}")
    print(f"  same-time stations   : {len(dataset_same_time)}")

    offline_features = build_features(
        station_id=STATION_ID,
        timestamp=target_ts,
        temperature_c=target["temperature_c"],
        relative_humidity_pct=target[
            "relative_humidity_pct"
        ],
        pressure_hpa=target["pressure_hpa"],
        history=dataset_history,
        all_station_history=dataset_same_time,
    )

    # ------------------------------------------------------------------
    # LIVE / POSTGRES CONTEXT
    #
    # This mirrors the data retrieval used by /ingest.
    # ------------------------------------------------------------------

    live_history = get_station_feature_history(
        STATION_ID,
        before_timestamp=target_ts,
        limit=96,
    )

    live_context = get_latest_station_context(
        target_ts,
        max_age_seconds=1800,
    )

    print()
    print("POSTGRES/LIVE CONTEXT:")
    print(f"  station history rows : {len(live_history)}")
    print(f"  spatial context rows : {len(live_context)}")

    if live_history:
        print(
            "  latest history timestamp : "
            f"{max(row['timestamp'] for row in live_history)}"
        )

    if live_context:
        print(
            "  latest context timestamp : "
            f"{max(row['timestamp'] for row in live_context)}"
        )

    live_history = pd.DataFrame(live_history)
    live_context = pd.DataFrame(live_context)

    live_features = build_features(
        station_id=STATION_ID,
        timestamp=target_ts,
        temperature_c=target["temperature_c"],
        relative_humidity_pct=target[
            "relative_humidity_pct"
        ],
        pressure_hpa=target["pressure_hpa"],
        history=live_history,
        all_station_history=live_context,
    )

    # ------------------------------------------------------------------
    # MODEL PREDICTION COMPARISON
    #
    # This is intentionally optional. If the model file is available,
    # compare the prediction on both feature vectors.
    # ------------------------------------------------------------------

    model_path = BACKEND_DIR / "model_anomaly_detector.pkl"

    print()
    print("MODEL COMPARISON:")

    try:
        import joblib

        if model_path.exists():
            model = joblib.load(model_path)

            offline_row = build_model_row(
                offline_features
            )
            live_row = build_model_row(
                live_features
            )

            offline_pred = int(
                model.predict(offline_row)[0]
            )
            live_pred = int(
                model.predict(live_row)[0]
            )

            offline_prob = float(
                model.predict_proba(offline_row)[0][1]
            )
            live_prob = float(
                model.predict_proba(live_row)[0][1]
            )

            print(
                f"  offline prediction : {offline_pred}"
            )
            print(
                f"  live prediction    : {live_pred}"
            )
            print(
                f"  offline anomaly p  : {offline_prob:.6f}"
            )
            print(
                f"  live anomaly p     : {live_prob:.6f}"
            )

        else:
            print(
                f"  Model not found: {model_path}"
            )

    except Exception as exc:
        print(
            "  Model comparison skipped:"
            f" {type(exc).__name__}: {exc}"
        )

    mismatch_count = print_feature_table(
        offline_features,
        live_features,
    )

    print()
    print("=" * 78)

    if mismatch_count == 0:
        print(
            "RESULT: LIVE FEATURE VECTOR MATCHES OFFLINE VECTOR."
        )
        print(
            "The next investigation target is inference/database "
            "state rather than feature construction."
        )
    else:
        print(
            "RESULT: LIVE FEATURE VECTOR DOES NOT MATCH OFFLINE VECTOR."
        )
        print(
            "Fix the first meaningful feature divergence before "
            "running another scenario evaluator."
        )

    print("=" * 78)


if __name__ == "__main__":
    main()
