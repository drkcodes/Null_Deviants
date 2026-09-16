from pathlib import Path
import pandas as pd
import numpy as np

DATASET = Path("ML training/SIH26073_AP_AWS_observations.csv")

print("Loading dataset...")
df = pd.read_csv(DATASET)

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["station_id"] = df["station_id"].astype(str)
df["anomaly_type"] = (
    df["anomaly_type"]
    .astype(str)
    .str.strip()
    .str.lower()
)

VALUE_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
]

WANTED = {
    "spike",
    "drop",
    "jump",
    "heatwave",
    "cold_spell",
}

# ---------------------------------------------------------
# Build 20-station timestamp set
# ---------------------------------------------------------

counts = (
    df.groupby("timestamp")["station_id"]
    .nunique()
)

full = set(counts[counts >= 20].index)

valid_windows = sorted(
    ts for ts in full
    if ts - pd.Timedelta(minutes=15) in full
)

print(f"Valid 20→20 windows: {len(valid_windows):,}")

valid_set = set(valid_windows)

candidates = df[
    df["timestamp"].isin(valid_set)
    & df["anomaly_type"].isin(WANTED)
].copy()

# ---------------------------------------------------------
# Create previous-observation lookup
# ---------------------------------------------------------

previous = df[
    ["station_id", "timestamp"] + VALUE_COLS
].copy()

previous["timestamp"] = (
    previous["timestamp"] + pd.Timedelta(minutes=15)
)

previous = previous.rename(
    columns={
        col: f"prev_{col}"
        for col in VALUE_COLS
    }
)

candidates = candidates.merge(
    previous,
    on=["station_id", "timestamp"],
    how="inner",
)

# ---------------------------------------------------------
# Calculate station deltas
# ---------------------------------------------------------

for col in VALUE_COLS:
    candidates[f"delta_{col}"] = (
        candidates[col]
        - candidates[f"prev_{col}"]
    )

# ---------------------------------------------------------
# Calculate network statistics for each timestamp
# ---------------------------------------------------------

network_rows = []

for ts in valid_windows:
    current = df[df["timestamp"] == ts]
    previous_ts = ts - pd.Timedelta(minutes=15)
    prev = df[df["timestamp"] == previous_ts]

    merged = current.merge(
        prev,
        on="station_id",
        suffixes=("_cur", "_prev"),
    )

    if len(merged) < 20:
        continue

    result = {
        "timestamp": ts,
    }

    for col in VALUE_COLS:
        delta = (
            merged[f"{col}_cur"]
            - merged[f"{col}_prev"]
        )

        median_delta = float(delta.median())

        meaningful = delta[
            delta.abs() >= 0.05
        ]

        if len(meaningful):
            coherence = float(
                (
                    np.sign(meaningful)
                    == np.sign(median_delta)
                ).mean()
            )
        else:
            coherence = 0.0

        result[f"{col}_median_delta"] = median_delta
        result[f"{col}_coherence"] = coherence
        result[f"{col}_median_abs_delta"] = float(
            delta.abs().median()
        )

    result["network_coherence"] = float(
        np.mean([
            result["temperature_c_coherence"],
            result["relative_humidity_pct_coherence"],
            result["pressure_hpa_coherence"],
        ])
    )

    network_rows.append(result)

network = pd.DataFrame(network_rows)

candidates = candidates.merge(
    network,
    on="timestamp",
    how="left",
)

# ---------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------

def score_row(row):
    temp = abs(row["delta_temperature_c"])
    rh = abs(row["delta_relative_humidity_pct"])
    pressure = abs(row["delta_pressure_hpa"])

    temp_net = max(row["temperature_c_median_abs_delta"], 0.25)
    rh_net = max(row["relative_humidity_pct_median_abs_delta"], 0.25)
    pressure_net = max(row["pressure_hpa_median_abs_delta"], 0.25)

    # Relative isolation from network movement.
    temp_iso = temp / temp_net
    rh_iso = rh / rh_net
    pressure_iso = pressure / pressure_net

    isolation = max(
        temp_iso,
        rh_iso,
        pressure_iso,
    )

    anomaly_type = row["anomaly_type"]

    if anomaly_type == "spike":
        score = (
            temp * 2.0
            + rh * 0.15
            + isolation * 2.0
        )

    elif anomaly_type == "drop":
        score = (
            temp * 2.0
            + rh * 0.15
            + isolation * 2.0
        )

    elif anomaly_type == "jump":
        score = (
            pressure * 2.0
            + temp * 0.5
            + isolation * 2.0
        )

    elif anomaly_type == "heatwave":
        score = (
            temp
            + rh * 0.15
        ) * row["network_coherence"]

    elif anomaly_type == "cold_spell":
        score = (
            temp
            + rh * 0.15
        ) * row["network_coherence"]

    else:
        score = 0.0

    return score


candidates["candidate_score"] = candidates.apply(
    score_row,
    axis=1,
)

# ---------------------------------------------------------
# Display top candidates
# ---------------------------------------------------------

for anomaly_type in sorted(WANTED):

    subset = candidates[
        candidates["anomaly_type"] == anomaly_type
    ].copy()

    subset = subset.sort_values(
        "candidate_score",
        ascending=False,
    )

    print()
    print("=" * 100)
    print(f"TOP {anomaly_type.upper()} CANDIDATES")
    print("=" * 100)

    columns = [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "delta_temperature_c",
        "delta_relative_humidity_pct",
        "delta_pressure_hpa",
        "network_coherence",
        "candidate_score",
    ]

    print(
        subset[columns]
        .head(15)
        .to_string(index=False)
    )

# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

output = Path("scored_network_candidates.csv")
candidates.to_csv(output, index=False)

print()
print(f"Saved: {output}")