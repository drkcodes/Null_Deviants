from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from database import get_station_feature_history


DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

STATION_ID = "AWS_AP01"
TARGET_TIMESTAMP = pd.Timestamp(
    "2025-12-31 00:00:00"
).tz_localize("Asia/Kolkata")


def find_column(df, candidates):
    lookup = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]

    raise RuntimeError(
        "Could not find column from: "
        + ", ".join(candidates)
    )


def load_dataset():
    df = pd.read_csv(DATASET_PATH)

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

    result = result.dropna(
        subset=["timestamp"]
    )

    result["timestamp"] = (
        result["timestamp"]
        .dt.tz_localize("Asia/Kolkata")
    )

    return result[
        result["station_id"] == STATION_ID
    ].sort_values(
        "timestamp"
    ).reset_index(drop=True)


def main():

    print("=" * 100)
    print("SIH26073 — HISTORY ALIGNMENT DIAGNOSTIC")
    print("=" * 100)
    print()
    print(f"Station : {STATION_ID}")
    print(f"Target  : {TARGET_TIMESTAMP}")
    print()

    # ========================================================
    # DATASET
    # ========================================================

    dataset = load_dataset()

    dataset_history = dataset[
        dataset["timestamp"] < TARGET_TIMESTAMP
    ].tail(96).copy()

    # ========================================================
    # POSTGRES
    # ========================================================

    live_history = get_station_feature_history(
        STATION_ID,
        before_timestamp=TARGET_TIMESTAMP,
        limit=96,
    )

    live_history = pd.DataFrame(
        live_history
    )

    if not live_history.empty:

        live_history["timestamp"] = pd.to_datetime(
            live_history["timestamp"],
            errors="coerce",
        )

        live_history = live_history.sort_values(
            "timestamp"
        ).reset_index(drop=True)

    print("ROW COUNTS")
    print("-" * 100)

    print(
        f"Dataset history : {len(dataset_history)}"
    )

    print(
        f"Postgres history: {len(live_history)}"
    )

    # ========================================================
    # PRINT BOTH SEQUENCES
    # ========================================================

    print()
    print(
        "LAST 20 HISTORICAL OBSERVATIONS BEFORE TARGET"
    )
    print("-" * 100)

    print(
        f"{'TIMESTAMP':<35}"
        f"{'CSV T':>12}"
        f"{'DB T':>12}"
        f"{'CSV RH':>12}"
        f"{'DB RH':>12}"
        f"{'CSV P':>12}"
        f"{'DB P':>12}"
    )

    print("-" * 100)

    csv_lookup = {
        row["timestamp"]: row
        for _, row in dataset_history.iterrows()
    }

    db_lookup = {
        row["timestamp"]: row
        for _, row in live_history.iterrows()
    }

    timestamps = sorted(
        set(csv_lookup) | set(db_lookup)
    )[-20:]

    mismatch_count = 0

    for ts in timestamps:

        csv_row = csv_lookup.get(ts)
        db_row = db_lookup.get(ts)

        csv_t = (
            csv_row["temperature_c"]
            if csv_row is not None
            else "MISSING"
        )

        db_t = (
            db_row["temperature_c"]
            if db_row is not None
            else "MISSING"
        )

        csv_rh = (
            csv_row["relative_humidity_pct"]
            if csv_row is not None
            else "MISSING"
        )

        db_rh = (
            db_row["relative_humidity_pct"]
            if db_row is not None
            else "MISSING"
        )

        csv_p = (
            csv_row["pressure_hpa"]
            if csv_row is not None
            else "MISSING"
        )

        db_p = (
            db_row["pressure_hpa"]
            if db_row is not None
            else "MISSING"
        )

        same = (
            csv_t == db_t
            and csv_rh == db_rh
            and csv_p == db_p
        )

        if not same:
            mismatch_count += 1
            marker = "<<< DIFF"
        else:
            marker = "OK"

        print(
            f"{str(ts):<35}"
            f"{str(csv_t):>12}"
            f"{str(db_t):>12}"
            f"{str(csv_rh):>12}"
            f"{str(db_rh):>12}"
            f"{str(csv_p):>12}"
            f"{str(db_p):>12}"
            f"  {marker}"
        )

    # ========================================================
    # COMPLETE 96-ROW COMPARISON
    # ========================================================

    print()
    print("=" * 100)
    print("COMPLETE 96-ROW ALIGNMENT")
    print("=" * 100)

    merged = pd.merge(
        dataset_history[
            [
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        ],
        live_history[
            [
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        ],
        on="timestamp",
        how="outer",
        suffixes=("_csv", "_db"),
        indicator=True,
    )

    value_diff = (
        merged[
            "_merge"
        ] != "both"
    )

    for column in [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]:

        value_diff |= (
            merged[f"{column}_csv"]
            .fillna(float("nan"))
            .ne(
                merged[f"{column}_db"]
                .fillna(float("nan"))
            )
        )

    differences = merged[
        value_diff
    ].sort_values("timestamp")

    print(
        f"Timestamp/value differences: "
        f"{len(differences)}"
    )

    if not differences.empty:

        print()

        print(
            differences.to_string(
                index=False
            )
        )

    # ========================================================
    # DUPLICATE TIMESTAMP CHECK
    # ========================================================

    print()
    print("=" * 100)
    print("DUPLICATE TIMESTAMP CHECK")
    print("=" * 100)

    csv_duplicates = dataset_history[
        dataset_history["timestamp"].duplicated(
            keep=False
        )
    ]

    db_duplicates = live_history[
        live_history["timestamp"].duplicated(
            keep=False
        )
    ]

    print(
        f"CSV duplicate timestamps: "
        f"{len(csv_duplicates)}"
    )

    print(
        f"DB duplicate timestamps : "
        f"{len(db_duplicates)}"
    )

    if not csv_duplicates.empty:

        print()
        print("CSV duplicates:")
        print(
            csv_duplicates.to_string(
                index=False
            )
        )

    if not db_duplicates.empty:

        print()
        print("DB duplicates:")
        print(
            db_duplicates.to_string(
                index=False
            )
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 100)

    if (
        len(dataset_history) == len(live_history)
        and len(differences) == 0
        and len(csv_duplicates) == 0
        and len(db_duplicates) == 0
    ):

        print(
            "RESULT: DATABASE HISTORY MATCHES DATASET."
        )

        print(
            "The feature divergence must therefore be "
            "caused after history retrieval."
        )

    else:

        print(
            "RESULT: DATABASE HISTORY DOES NOT MATCH DATASET."
        )

        print(
            "This is the issue to fix before further "
            "model/evaluator work."
        )

    print("=" * 100)


if __name__ == "__main__":
    main()