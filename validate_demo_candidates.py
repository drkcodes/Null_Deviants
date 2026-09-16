from pathlib import Path
import pandas as pd
import numpy as np

DATASET = Path("ML training/SIH26073_AP_AWS_observations.csv")
SCORED = Path("scored_network_candidates.csv")

print("Loading data...")
df = pd.read_csv(DATASET)
candidates = pd.read_csv(SCORED)

df["timestamp"] = pd.to_datetime(df["timestamp"])
candidates["timestamp"] = pd.to_datetime(candidates["timestamp"])

VALUE_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
]

# ---------------------------------------------------------
# Evaluate the strongest candidates for each scenario
# using the production evidence rules.
# ---------------------------------------------------------

for anomaly_type in [
    "spike",
    "drop",
    "jump",
    "heatwave",
    "cold_spell",
]:

    subset = (
        candidates[
            candidates["anomaly_type"] == anomaly_type
        ]
        .sort_values("candidate_score", ascending=False)
        .head(30)
    )

    results = []

    for _, row in subset.iterrows():

        ts = row["timestamp"]
        station = row["station_id"]

        current = df[df["timestamp"] == ts].copy()

        previous = df[
            df["timestamp"]
            == ts - pd.Timedelta(minutes=15)
        ].copy()

        if len(current) < 20 or len(previous) < 20:
            continue

        merged = current.merge(
            previous,
            on="station_id",
            suffixes=("_cur", "_prev"),
        )

        if len(merged) < 20:
            continue

        stats = {}

        for col in VALUE_COLS:

            delta = (
                merged[f"{col}_cur"]
                - merged[f"{col}_prev"]
            )

            median_delta = float(delta.median())

            median_abs_delta = float(
                delta.abs().median()
            )

            meaningful = delta[
                delta.abs() >= 0.05
            ]

            if len(meaningful) > 0:
                coherence = float(
                    (
                        np.sign(meaningful)
                        == np.sign(median_delta)
                    ).mean()
                )
            else:
                coherence = 0.0

            target = merged[
                merged["station_id"] == station
            ]

            if target.empty:
                continue

            target_delta = float(
                target.iloc[0][f"{col}_cur"]
                - target.iloc[0][f"{col}_prev"]
            )

            stats[col] = {
                "median_delta": median_delta,
                "median_abs_delta": median_abs_delta,
                "coherence": coherence,
                "target_delta": target_delta,
            }

        temp = stats["temperature_c"]
        rh = stats["relative_humidity_pct"]
        pressure = stats["pressure_hpa"]

        network_coherence = np.mean([
            temp["coherence"],
            rh["coherence"],
            pressure["coherence"],
        ])

        temp_event = (
            abs(temp["median_delta"]) >= 3.0
            and temp["coherence"] >= 0.70
        )

        rh_event = (
            abs(rh["median_delta"]) >= 8.0
            and rh["coherence"] >= 0.70
        )

        pressure_event = (
            abs(pressure["median_delta"]) >= 3.0
            and pressure["coherence"] >= 0.70
        )

        regional_event = (
            (
                int(temp_event)
                + int(rh_event)
                + int(pressure_event)
            ) >= 1
            and network_coherence >= 0.70
        )

        isolation_scores = []

        for item in stats.values():

            network_abs = max(
                item["median_abs_delta"],
                0.25,
            )

            ratio = (
                abs(item["target_delta"])
                / network_abs
            )

            isolation_scores.append(
                max(
                    0.0,
                    min(
                        (ratio - 1.0) / 4.0,
                        1.0,
                    ),
                )
            )

        isolation = (
            max(isolation_scores)
            if isolation_scores
            else 0.0
        )

        results.append({
            "station": station,
            "timestamp": ts,
            "temperature": round(
                row["temperature_c"], 3
            ),
            "humidity": round(
                row["relative_humidity_pct"], 3
            ),
            "pressure": round(
                row["pressure_hpa"], 3
            ),

            "dT": round(
                temp["target_delta"], 3
            ),
            "dRH": round(
                rh["target_delta"], 3
            ),
            "dP": round(
                pressure["target_delta"], 3
            ),

            "median_dT": round(
                temp["median_delta"], 3
            ),
            "median_dRH": round(
                rh["median_delta"], 3
            ),
            "median_dP": round(
                pressure["median_delta"], 3
            ),

            "T_coh": round(
                temp["coherence"], 3
            ),
            "RH_coh": round(
                rh["coherence"], 3
            ),
            "P_coh": round(
                pressure["coherence"], 3
            ),

            "network_coherence": round(
                network_coherence, 3
            ),

            "regional_event": regional_event,
            "isolation": round(
                isolation, 3
            ),
        })

    result_df = pd.DataFrame(results)

    print()
    print("=" * 120)
    print(anomaly_type.upper())
    print("=" * 120)

    if result_df.empty:
        print("NO VALID CANDIDATES")
        continue

    if anomaly_type in {"heatwave", "cold_spell"}:

        result_df = result_df[
            result_df["regional_event"]
        ].sort_values(
            ["network_coherence"],
            ascending=False,
        )

    else:

        result_df = result_df.sort_values(
            ["isolation"],
            ascending=False,
        )

    print(
        result_df.head(10).to_string(
            index=False
        )
    )

print()
print("Validation complete.")