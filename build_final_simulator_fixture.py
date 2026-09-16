from pathlib import Path
import pandas as pd
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR

DATASET = PROJECT_DIR / "ML training" / "SIH26073_AP_AWS_observations.csv"
BACKEND = PROJECT_DIR / "BACKEND"

FIXTURE = BACKEND / "SIH26073_AP_AWS_observations.csv"
HISTORY = BACKEND / "simulator_history_seed.csv"
MANIFEST = BACKEND / "simulator_fixture_manifest.csv"

VALUE_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
]

STATIONS = sorted(
    [f"AWS_AP{i:02d}" for i in range(1, 21)]
)

print("=" * 90)
print("BUILD FINAL SIMULATOR FIXTURE")
print("=" * 90)

print("\nLoading full SIH dataset...")
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
# Build 20 -> 20 valid timestamps
# ---------------------------------------------------------

counts = (
    df.groupby("timestamp")["station_id"]
    .nunique()
)

full_network = set(
    counts[counts >= 20].index
)

valid_windows = sorted(
    ts for ts in full_network
    if ts - pd.Timedelta(minutes=15) in full_network
)

valid_set = set(valid_windows)

print(f"20->20 valid windows: {len(valid_windows):,}")

# ---------------------------------------------------------
# Build previous observation lookup
# ---------------------------------------------------------

prev = df[
    ["station_id", "timestamp"] + VALUE_COLS
].copy()

prev["timestamp"] = (
    prev["timestamp"] + pd.Timedelta(minutes=15)
)

prev = prev.rename(
    columns={
        c: f"prev_{c}"
        for c in VALUE_COLS
    }
)

# ---------------------------------------------------------
# Calculate network context
# ---------------------------------------------------------

network_rows = []

for ts in valid_windows:

    current = df[
        df["timestamp"] == ts
    ]

    previous = df[
        df["timestamp"]
        == ts - pd.Timedelta(minutes=15)
    ]

    merged = current.merge(
        previous,
        on="station_id",
        suffixes=("_cur", "_prev"),
    )

    if len(merged) != 20:
        continue

    item = {
        "timestamp": ts,
    }

    for col in VALUE_COLS:

        delta = (
            merged[f"{col}_cur"]
            - merged[f"{col}_prev"]
        )

        median_delta = float(
            delta.median()
        )

        median_abs_delta = float(
            delta.abs().median()
        )

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

        item[f"{col}_median_delta"] = median_delta
        item[f"{col}_median_abs_delta"] = (
            median_abs_delta
        )
        item[f"{col}_coherence"] = coherence

    item["network_coherence"] = float(
        np.mean([
            item["temperature_c_coherence"],
            item["relative_humidity_pct_coherence"],
            item["pressure_hpa_coherence"],
        ])
    )

    network_rows.append(item)

network = pd.DataFrame(network_rows)

# ---------------------------------------------------------
# Candidate table
# ---------------------------------------------------------

candidates = df[
    df["timestamp"].isin(valid_set)
    & df["anomaly_type"].isin(
        {"spike", "drop", "jump"}
    )
].copy()

candidates = candidates.merge(
    prev,
    on=["station_id", "timestamp"],
    how="inner",
)

for col in VALUE_COLS:
    candidates[f"delta_{col}"] = (
        candidates[col]
        - candidates[f"prev_{col}"]
    )

candidates = candidates.merge(
    network,
    on="timestamp",
    how="inner",
)

# ---------------------------------------------------------
# Isolation score using production formula
# ---------------------------------------------------------

def isolation_score(row):

    scores = []

    for col in VALUE_COLS:

        network_abs = max(
            float(row[f"{col}_median_abs_delta"]),
            0.25,
        )

        ratio = (
            abs(float(row[f"delta_{col}"]))
            / network_abs
        )

        score = max(
            0.0,
            min(
                (ratio - 1.0) / 4.0,
                1.0,
            ),
        )

        scores.append(score)

    return max(scores)


candidates["isolation"] = candidates.apply(
    isolation_score,
    axis=1,
)

# ---------------------------------------------------------
# Select safe candidates per station/scenario
# ---------------------------------------------------------

selected = []

for scenario in ["spike", "drop", "jump"]:

    for station in STATIONS:

        subset = candidates[
            (candidates["station_id"] == station)
            & (
                candidates["anomaly_type"]
                == scenario
            )
        ].copy()

        if subset.empty:
            raise RuntimeError(
                f"No candidates for {station} / {scenario}"
            )

        # Reasonable physical/data bounds.
        if scenario == "spike":

            subset = subset[
                subset["delta_temperature_c"].between(
                    8, 30
                )
                & subset["temperature_c"].between(
                    0, 55
                )
                & subset["relative_humidity_pct"].between(
                    0, 100
                )
            ]

        elif scenario == "drop":

            subset = subset[
                subset["delta_temperature_c"].between(
                    -30, -8
                )
                & subset["temperature_c"].between(
                    -5, 45
                )
                & subset["relative_humidity_pct"].between(
                    0, 100
                )
            ]

        elif scenario == "jump":

            subset = subset[
                subset["delta_pressure_hpa"].between(
                    8, 30
                )
                & subset["pressure_hpa"].between(
                    850, 1100
                )
                & subset["relative_humidity_pct"].between(
                    0, 100
                )
            ]

        if subset.empty:
            raise RuntimeError(
                f"No safe candidate for "
                f"{station} / {scenario}"
            )

        # Prefer strong isolation, then stronger
        # scenario-specific movement.
        if scenario in {"spike", "drop"}:

            subset["strength"] = (
                subset["delta_temperature_c"]
                .abs()
            )

        else:

            subset["strength"] = (
                subset["delta_pressure_hpa"]
                .abs()
            )

        subset = subset.sort_values(
            ["isolation", "strength"],
            ascending=False,
        )

        selected.append(
            subset.iloc[0]
        )

selected = pd.DataFrame(selected)

# ---------------------------------------------------------
# Regional cases
# ---------------------------------------------------------

regional_specs = [
    (
        "heatwave",
        pd.Timestamp("2025-03-14 15:00:00"),
    ),
    (
        "cold_spell",
        pd.Timestamp("2025-01-27 00:00:00"),
    ),
]

regional_rows = []

for scenario, ts in regional_specs:

    current = df[
        df["timestamp"] == ts
    ].copy()

    if len(current) != 20:
        raise RuntimeError(
            f"{scenario}: expected 20 stations, "
            f"found {len(current)}"
        )

    previous = df[
        df["timestamp"]
        == ts - pd.Timedelta(minutes=15)
    ]

    if len(previous) != 20:
        raise RuntimeError(
            f"{scenario}: previous snapshot "
            f"does not contain 20 stations"
        )

    regional_rows.append(
        current.assign(
            selected_scenario=scenario,
            regional_event=True,
        )
    )

regional = pd.concat(
    regional_rows,
    ignore_index=True,
)

# ---------------------------------------------------------
# Build final 100-row fixture
# ---------------------------------------------------------

isolated_fixture = selected[
    [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
    ]
].copy()

isolated_fixture["selected_scenario"] = (
    selected["anomaly_type"]
)

isolated_fixture["regional_event"] = False

regional_fixture = regional[
    [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "selected_scenario",
        "regional_event",
    ]
].copy()

fixture = pd.concat(
    [
        isolated_fixture,
        regional_fixture,
    ],
    ignore_index=True,
)

# Remove accidental duplicates.
fixture = fixture.drop_duplicates(
    subset=["station_id", "selected_scenario"]
)

if len(fixture) != 100:
    raise RuntimeError(
        f"Expected exactly 100 fixture rows, "
        f"got {len(fixture)}"
    )

fixture["anomaly_type"] = (
    fixture["selected_scenario"]
)

fixture = fixture[
    [
        "station_id",
        "timestamp",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "anomaly_type",
    ]
].sort_values(
    ["anomaly_type", "station_id"]
)

# ---------------------------------------------------------
# Build history seed
#
# For every selected fixture row, retain:
#   1. Previous 96 observations for the target station
#   2. All 20 stations at the current timestamp
#   3. All 20 stations at the previous timestamp
#
# This preserves both temporal and spatial context required
# by the production simulator.
# ---------------------------------------------------------

history_parts = []

for _, row in fixture.iterrows():

    station = row["station_id"]
    ts = row["timestamp"]

    # -----------------------------------------------------
    # 1. Target-station temporal history
    # -----------------------------------------------------

    station_history = df[
        (df["station_id"] == station)
        & (df["timestamp"] < ts)
    ].sort_values("timestamp")

    if len(station_history) < 96:
        raise RuntimeError(
            f"Insufficient history for "
            f"{station} @ {ts}"
        )

    history_parts.append(
        station_history.tail(96)[
            [
                "station_id",
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        ]
    )

    # -----------------------------------------------------
    # 2. Current 20-station network snapshot
    # -----------------------------------------------------

    current_network = df[
        df["timestamp"] == ts
    ]

    if current_network["station_id"].nunique() != 20:
        raise RuntimeError(
            f"Current network context incomplete for "
            f"{station} @ {ts}: "
            f"{current_network['station_id'].nunique()} stations"
        )

    history_parts.append(
        current_network[
            [
                "station_id",
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        ]
    )

    # -----------------------------------------------------
    # 3. Previous 20-station network snapshot
    # -----------------------------------------------------

    previous_ts = (
        ts - pd.Timedelta(minutes=15)
    )

    previous_network = df[
        df["timestamp"] == previous_ts
    ]

    if previous_network["station_id"].nunique() != 20:
        raise RuntimeError(
            f"Previous network context incomplete for "
            f"{station} @ {ts}: "
            f"{previous_network['station_id'].nunique()} stations"
        )

    history_parts.append(
        previous_network[
            [
                "station_id",
                "timestamp",
                "temperature_c",
                "relative_humidity_pct",
                "pressure_hpa",
            ]
        ]
    )

history = pd.concat(
    history_parts,
    ignore_index=True,
)

history = history.drop_duplicates(
    subset=["station_id", "timestamp"]
).sort_values(
    ["station_id", "timestamp"]
)


# ---------------------------------------------------------
# Manifest
# ---------------------------------------------------------

manifest_rows = []

for _, row in fixture.iterrows():

    station = row["station_id"]
    ts = row["timestamp"]
    scenario = row["anomaly_type"]

    station_history = history[
        history["station_id"] == station
    ]

    prior = station_history[
        station_history["timestamp"] < ts
    ]

    previous_ts = ts - pd.Timedelta(minutes=15)

    current_network = df[
        df["timestamp"] == ts
    ]

    previous_network = df[
        df["timestamp"] == previous_ts
    ]

    manifest_rows.append({
        "station_id": station,
        "scenario": scenario,
        "timestamp": ts,
        "prior_history_rows": len(prior),
        "current_network_stations": (
            current_network["station_id"].nunique()
        ),
        "previous_network_stations": (
            previous_network["station_id"].nunique()
        ),
    })

manifest = pd.DataFrame(
    manifest_rows
)

# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

print("\nFinal fixture counts:")
print(
    fixture["anomaly_type"]
    .value_counts()
    .sort_index()
)

print(
    "\nUnique station/scenario pairs:",
    fixture[
        ["station_id", "anomaly_type"]
    ].drop_duplicates().shape[0],
)

print(
    "History rows:",
    len(history),
)

print(
    "History stations:",
    history["station_id"].nunique(),
)

assert (
    manifest["prior_history_rows"] >= 96
).all()

assert (
    manifest["current_network_stations"] == 20
).all()

assert (
    manifest["previous_network_stations"] == 20
).all()

# ---------------------------------------------------------
# Validate generated history seed itself
# ---------------------------------------------------------

for _, row in fixture.iterrows():

    station = row["station_id"]
    ts = row["timestamp"]
    previous_ts = (
        ts - pd.Timedelta(minutes=15)
    )

    current_seed = history[
        history["timestamp"] == ts
    ]

    previous_seed = history[
        history["timestamp"] == previous_ts
    ]

    current_count = (
        current_seed["station_id"].nunique()
    )

    previous_count = (
        previous_seed["station_id"].nunique()
    )

    if current_count != 20:
        raise RuntimeError(
            f"Generated seed missing current "
            f"network context for {station} @ {ts}: "
            f"{current_count}/20 stations"
        )

    if previous_count != 20:
        raise RuntimeError(
            f"Generated seed missing previous "
            f"network context for {station} @ {ts}: "
            f"{previous_count}/20 stations"
        )

# ---------------------------------------------------------
# Write files
# ---------------------------------------------------------

fixture.to_csv(
    FIXTURE,
    index=False,
)

history.to_csv(
    HISTORY,
    index=False,
)

manifest.to_csv(
    MANIFEST,
    index=False,
)

print("\n" + "=" * 90)
print("FINAL FIXTURE CREATED")
print("=" * 90)

print(f"Fixture : {FIXTURE}")
print(f"Rows    : {len(fixture)}")

print(f"History : {HISTORY}")
print(f"Rows    : {len(history)}")

print(f"Manifest: {MANIFEST}")
print(f"Rows    : {len(manifest)}")

print("\nALL VALIDATIONS PASSED.")