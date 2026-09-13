from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from database import get_latest_station_context
from feature_engineering import build_features

DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

STATION_ID = "AWS_AP01"
TARGET = pd.Timestamp("2025-12-30 23:45:00").tz_localize("Asia/Kolkata")


def find_col(df, names):
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    raise RuntimeError(f"Missing one of: {names}")


def load_dataset():
    df = pd.read_csv(DATASET_PATH)

    station = find_col(df, ["station_id", "station", "aws_station_id"])
    ts = find_col(df, ["timestamp", "datetime", "date_time", "time"])
    t = find_col(df, ["temperature_c", "temperature", "temp_c"])
    rh = find_col(df, ["relative_humidity_pct", "relative_humidity", "humidity_pct", "humidity"])
    p = find_col(df, ["pressure_hpa", "atmospheric_pressure_hpa", "pressure"])

    out = pd.DataFrame({
        "station_id": df[station].astype(str),
        "timestamp": pd.to_datetime(df[ts], errors="coerce"),
        "temperature_c": pd.to_numeric(df[t], errors="coerce"),
        "relative_humidity_pct": pd.to_numeric(df[rh], errors="coerce"),
        "pressure_hpa": pd.to_numeric(df[p], errors="coerce"),
    }).dropna(subset=["timestamp"])

    out["timestamp"] = out["timestamp"].dt.tz_localize("Asia/Kolkata")
    return out


def main():
    print("=" * 100)
    print("SIH26073 — SPATIAL CONTEXT ALIGNMENT")
    print("=" * 100)
    print(f"Station: {STATION_ID}")
    print(f"Target : {TARGET}")
    print()

    data = load_dataset()

    csv_context = data[data["timestamp"] == TARGET].copy()
    db_context = pd.DataFrame(
        get_latest_station_context(
            TARGET,
            max_age_seconds=1800,
        )
    )

    if not db_context.empty:
        db_context["timestamp"] = pd.to_datetime(
            db_context["timestamp"],
            errors="coerce",
        )

    print(f"CSV same-time rows: {len(csv_context)}")
    print(f"DB context rows   : {len(db_context)}")
    print()

    merged = pd.merge(
        csv_context,
        db_context,
        on="station_id",
        how="outer",
        suffixes=("_csv", "_db"),
        indicator=True,
    )

    print(
        f"{'STATION':<14}"
        f"{'CSV T':>10}{'DB T':>10}"
        f"{'CSV RH':>10}{'DB RH':>10}"
        f"{'CSV P':>12}{'DB P':>12}"
        f"   STATUS"
    )
    print("-" * 100)

    differences = 0

    for _, row in merged.sort_values("station_id").iterrows():
        def val(name):
            x = row[name]
            return "MISSING" if pd.isna(x) else f"{float(x):.3f}"

        same = (
            row["_merge"] == "both"
            and float(row["temperature_c_csv"]) == float(row["temperature_c_db"])
            and float(row["relative_humidity_pct_csv"]) == float(row["relative_humidity_pct_db"])
            and float(row["pressure_hpa_csv"]) == float(row["pressure_hpa_db"])
        )

        if not same:
            differences += 1

        print(
            f"{str(row['station_id']):<14}"
            f"{val('temperature_c_csv'):>10}"
            f"{val('temperature_c_db'):>10}"
            f"{val('relative_humidity_pct_csv'):>10}"
            f"{val('relative_humidity_pct_db'):>10}"
            f"{val('pressure_hpa_csv'):>12}"
            f"{val('pressure_hpa_db'):>12}"
            f"   {'OK' if same else '<<< DIFF'}"
        )

    print()
    print("=" * 100)
    print(f"Station context differences: {differences}")
    print("=" * 100)

    # Explicitly show AP01's spatial neighbors as calculated by the feature engine.
    stations_file = BACKEND_DIR / "stations.csv"
    if stations_file.exists():
        stations = pd.read_csv(stations_file)
        row = stations[
            stations["station_id"].astype(str) == STATION_ID
        ]
        if not row.empty:
            print()
            print("STATION METADATA")
            print("-" * 100)
            print(row.to_string(index=False))

            nearest = str(row.iloc[0]["nearest_station_id"])
            print()
            print(f"AP01 nearest station according to stations.csv: {nearest}")

    # Compare the four spatial features directly.
    target = csv_context[csv_context["station_id"] == STATION_ID].iloc[0]

    csv_features = build_features(
        station_id=STATION_ID,
        timestamp=TARGET,
        temperature_c=target["temperature_c"],
        relative_humidity_pct=target["relative_humidity_pct"],
        pressure_hpa=target["pressure_hpa"],
        history=data[
            (data["station_id"] == STATION_ID)
            & (data["timestamp"] < TARGET)
        ].tail(96),
        all_station_history=csv_context,
    )

    db_features = build_features(
        station_id=STATION_ID,
        timestamp=TARGET,
        temperature_c=target["temperature_c"],
        relative_humidity_pct=target["relative_humidity_pct"],
        pressure_hpa=target["pressure_hpa"],
        history=data[
            (data["station_id"] == STATION_ID)
            & (data["timestamp"] < TARGET)
        ].tail(96),
        all_station_history=db_context,
    )

    print()
    print("SPATIAL FEATURE DIFFERENCE")
    print("-" * 100)

    for feature in [
        "spatial_temp_diff",
        "spatial_humidity_diff",
        "spatial_pressure_diff",
        "regional_temp_zscore",
    ]:
        print(
            f"{feature:<30}"
            f"CSV={csv_features[feature]:>16.9f}   "
            f"DB={db_features[feature]:>16.9f}   "
            f"DIFF={db_features[feature] - csv_features[feature]:>16.9f}"
        )

    print()
    if differences == 0:
        print("RESULT: ALL 20 SPATIAL CONTEXT ROWS MATCH.")
        print("The discrepancy is inside spatial feature calculation/context metadata.")
    else:
        print("RESULT: DATABASE SPATIAL CONTEXT DOES NOT MATCH THE DATASET.")
        print("Fix the context retrieval before changing the ML model.")


if __name__ == "__main__":
    main()
