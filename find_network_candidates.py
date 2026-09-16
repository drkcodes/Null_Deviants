from pathlib import Path
import pandas as pd

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

print(f"Rows: {len(df):,}")
print(f"Stations: {df['station_id'].nunique()}")

# ---------------------------------------------------------
# 1. Find timestamps with all 20 stations
# ---------------------------------------------------------

station_counts = (
    df.groupby("timestamp")["station_id"]
    .nunique()
)

full_network_timestamps = station_counts[
    station_counts >= 20
].index

print()
print(f"20-station timestamps: {len(full_network_timestamps):,}")

# ---------------------------------------------------------
# 2. Require previous 15-minute 20-station snapshot too
# ---------------------------------------------------------

full_network_set = set(full_network_timestamps)

valid_windows = []

for ts in full_network_timestamps:
    previous = ts - pd.Timedelta(minutes=15)

    if previous in full_network_set:
        valid_windows.append(ts)

valid_windows = sorted(valid_windows)

print(f"20→20 valid windows: {len(valid_windows):,}")

if valid_windows:
    print()
    print("First valid windows:")
    for ts in valid_windows[:20]:
        print(" ", ts)

# ---------------------------------------------------------
# 3. Inspect supported anomaly types inside valid windows
# ---------------------------------------------------------

wanted = {
    "spike",
    "drop",
    "jump",
    "heatwave",
    "cold_spell",
}

valid_set = set(valid_windows)

candidates = df[
    df["timestamp"].isin(valid_set)
    & df["anomaly_type"].isin(wanted)
].copy()

print()
print("Candidate rows by anomaly type:")
print(candidates["anomaly_type"].value_counts().sort_index())

# ---------------------------------------------------------
# 4. Print representative candidates
# ---------------------------------------------------------

print()
print("=" * 80)
print("REPRESENTATIVE CANDIDATES")
print("=" * 80)

for anomaly_type in sorted(wanted):
    subset = candidates[
        candidates["anomaly_type"] == anomaly_type
    ].copy()

    if subset.empty:
        print(f"\n{anomaly_type}: NONE")
        continue

    print(f"\n{anomaly_type}: {len(subset):,} candidates")

    # Show first 10 unique station/timestamp combinations
    sample = (
        subset[
            [
                "station_id",
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        ]
        .drop_duplicates()
        .head(10)
    )

    print(sample.to_string(index=False))

# ---------------------------------------------------------
# 5. Save candidates for detailed analysis
# ---------------------------------------------------------

output = Path("network_valid_candidates.csv")

candidates.to_csv(output, index=False)

print()
print(f"Saved: {output}")