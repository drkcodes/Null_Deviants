# SIH26073 — Andhra Pradesh AWS Anomaly Detection Dataset (v1, FINAL)

Synthetic training/evaluation dataset for AI/ML-based intelligent anomaly
detection on Automatic Weather Stations, scoped to Andhra Pradesh.

## Files

| File | Description |
|---|---|
| `stations.csv` | 20 station metadata records (real AP locations) |
| `SIH26073_AP_AWS_observations.csv` | Main dataset, 700,800 rows × 76 columns |
| `SIH26073_AP_AWS_observations.csv.gz` | Same data, gzip-compressed (~95MB vs ~325MB). Load directly with `pd.read_csv('file.csv.gz')` — pandas handles gzip natively, no need to unzip. |
| `allowed_features.txt` | Plain-text list of which columns are safe ML inputs vs which are ground truth/labels |

## What this is, and what it isn't

This is **synthetic data**: a real physical climate model (seasonal +
diurnal cycles for temperature/humidity/pressure, elevation adjustment,
region-specific climate differences) with **controlled, labeled faults
injected on top**. It is not scraped or derived from IMD or DES-AP's actual
sensor readings. Climatology baseline values (monthly max/min temp, RH,
pressure by region) are reasonable approximations based on general
knowledge of Andhra Pradesh's climate patterns (coastal vs. Rayalaseema),
**not pulled from a verified official IMD climate-normals dataset** — if
you want to cite exact climate normal figures in your report/pitch, cross-
check the specific numbers against an IMD source first rather than citing
this dataset's baseline constants as official data.

This is appropriate for: building and testing your ML pipeline, validating
your feature engineering, training a first working anomaly detection
model, and demoing the system end-to-end. It is not a substitute for real
AWS sensor data for final calibration/validation — that step still needs
real IMD or DES-AP data if/when access allows.

Reproducible: fixed random seed (42). Re-running the generation scripts
produces an identical dataset.

## Station coverage

20 stations across Andhra Pradesh, real district-level coordinates, split
12 Coastal / 8 Rayalaseema to capture AP's genuine climate contrast (humid
cyclone-exposed coast vs. dry drought-prone interior). See `stations.csv`
for exact lat/long/elevation and each station's nearest-neighbour pairing
(used for spatial cross-validation features). Nearest-neighbour distances
range roughly 30–130 km — reflects real inter-city spacing in AP, not an
idealized dense grid.

Elevations are approximate (documented as such, not independently
verified against a survey source) — reasonable for realistic pressure/
temperature adjustment, not for engineering-grade precision.

## Time coverage

Full year 2025, 15-minute sampling → 35,040 timestamps × 20 stations =
**700,800 rows**.

## Core labeling philosophy — read this before training

`anomaly_flag = True` for **two distinct causes**, disambiguated by
`weather_or_sensor`:

1. **Genuine extreme weather** (`weather_or_sensor = "weather"`) — heatwave
   or cold-spell episodes, applied *region-wide and simultaneously* across
   all stations in that region (spatially coherent, matching how real
   extreme weather actually behaves).
2. **Sensor faults** (`weather_or_sensor = "sensor"`) — injected into a
   *single station* at a time, spatially isolated (neighbours stay normal).

This mirrors the actual problem statement's core requirement: the system
must distinguish "this reading is unusual because of real weather" from
"this reading is unusual because the sensor is broken" — not just flag
outliers. Your model/pipeline should be evaluated on **both** tasks:
anomaly detection (`anomaly_flag`) and root-cause classification
(`weather_or_sensor`, `anomaly_type`).

Weather events (n≈14) and sensor fault episodes (~60 per station across
all fault types) were scheduled independently, so rare overlaps (a fault
happening to occur during a heatwave window) are possible and left as-is —
this is realistic, not a bug. In such rows the sensor-fault label takes
precedence, since it's the more specific/actionable classification.

## Anomaly taxonomy actually implemented

| Category | Type | Notes |
|---|---|---|
| Temperature | spike, drop, freeze/stuck, drift | |
| Humidity | spike, drop, freeze/stuck, drift | |
| Pressure | jump, drop, freeze/stuck, drift | "jump" = pressure's spike equivalent, sustained rather than instantaneous |
| Cross-parameter | multivariate_inconsistency | Humidity pushed up while temperature stays normal, producing a physically impossible dew point (dew point > air temp) |
| Data/communication | missing_data | 1–4 reading gap, one or more params |
| Data/communication | communication_failure | 1–6 hour gap, all 3 params simultaneously (station goes offline) |
| Data/communication | duplicate_observation | Exact repeat of previous reading across all 3 params, single timestamp |
| Data/communication | out_of_order_timestamp | Two adjacent readings' timestamps swapped (see note below) |
| Data/communication | invalid_value | Physically implausible sentinel-like values (e.g. -50°C, 105% RH, 850 hPa) |
| Genuine weather | heatwave, cold_spell | Region-wide, multi-day, spatially coherent |

Actual achieved counts (this run):
- Overall anomaly rate: **8.56%** of all rows
- Weather-caused: 45,887 rows / Sensor-fault-caused: 14,069 rows
- Full per-type breakdown available via `df.anomaly_type.value_counts()`

**Important design note on `out_of_order_timestamp`:** all lag, rolling,
z-score, and spatial features were computed using the *true chronological
sequence* (i.e., the order in which readings actually occurred), and only
afterward were two adjacent rows' `timestamp` values swapped. This models
"the logged timestamp field got corrupted/misordered" rather than "the
underlying measurement sequence integrity is broken" — a defensible and
realistic interpretation of what this fault type represents in a real
telemetry system with a buffering layer. If your team wants a stricter
interpretation (features recomputed on the *scrambled* order), that would
require regenerating this subset — flag it if that distinction matters for
your specific demo scenario.

## Ground truth vs. ML input — do not mix these up

**NEVER feed these into a model as input features:**
```
true_temperature_c
true_relative_humidity_pct
true_pressure_hpa
anomaly_flag
anomaly_type
anomaly_category
severity
weather_or_sensor
fault_component
```
The `true_*` columns exist only so you can (a) evaluate how close a
"corrected value" prediction is to reality, and (b) sanity-check your
synthetic data generation itself. The `anomaly_flag`/`anomaly_type`/etc.
columns are your **training targets**, not inputs — using them as features
would let the model cheat by looking at the answer.

**Everything else (67 columns) is safe to use as ML input.** Full list in
`allowed_features.txt`.

## Column dictionary

### Identification / context (9 cols)
`station_id`, `region`, `timestamp`, `date`, `hour` (decimal, e.g. 14.25 =
2:15pm), `day_of_year`, `month`, `season` (winter/summer/monsoon/
post_monsoon — standard 4-season IMD-style classification), `is_daytime`

### Ground truth — EXCLUDE from ML input (3 cols)
`true_temperature_c`, `true_relative_humidity_pct`, `true_pressure_hpa`

### Raw observations — ML INPUT (3 cols)
`temperature_c`, `relative_humidity_pct`, `pressure_hpa` — what the sensor
actually reported, faults included. NaN where a missing-data or
communication-failure fault was injected.

### Missing-value indicators (3 cols)
`is_missing_temperature`, `is_missing_humidity`, `is_missing_pressure`

### Lag & rate-of-change (18 cols)
Per parameter (temperature/humidity/pressure): `_lag_15min`, `_lag_1h`,
`_lag_3h`, `_lag_24h`, `_roc_15min`, `_roc_1h`. Computed from raw values,
per station, chronologically ordered (pre-timestamp-swap order — see note
above).

### Rolling statistics & z-score (15 cols)
Per parameter: `_rollmean_1h`, `_rollstd_1h`, `_rollmean_6h`,
`_rollstd_6h`, `_zscore_6h`. Rolling windows use `min_periods` so the
first few hours of each station's series aren't all-NaN.

### Stuck-value detection (3 cols)
`_stuck_count` per parameter — consecutive identical-reading run length,
resets to 0 on any change or NaN. Directly useful for freeze/duplicate
detection.

### Multivariate consistency (3 cols)
`dew_point_estimate_c` (Magnus formula from raw T & RH), `dew_point_
deficit_c` (temperature − dew point; should be ≥0 physically),
`physically_implausible_flag` (1 when deficit < -0.5, i.e. dew point
exceeds air temperature — a physical impossibility signalling likely
sensor/multivariate fault).

### Spatial (11 cols)
`nearest_station_id`, `nearest_station_distance_km` (static per station),
`nearest_station_temp/humidity/pressure` (that neighbour's reading at the
same timestamp), `spatial_*_diff` (this station minus neighbour),
`regional_mean_temp`, `regional_std_temp`, `regional_temp_zscore` (vs. all
stations in the same region at that timestamp — this is your primary
"is this genuinely regional weather or an isolated station issue?" signal).

### Weather context — usable as ML input (2 cols)
`heatwave_context_flag`, `cold_spell_context_flag` — these represent
*known meteorological context* (the kind of thing a real system would have
from IMD warnings), not an answer leak, so they're legitimately usable as
input features, unlike the anomaly labels.

### Labels / targets — EXCLUDE from ML input (6 cols)
`anomaly_flag`, `anomaly_type`, `anomaly_category`, `severity`
(LOW/MEDIUM/HIGH/none), `weather_or_sensor` (weather/sensor/none),
`fault_component` (which parameter(s) affected, or 'none')

## Recommended next steps

1. **Time-based split**, not random shuffle — e.g. train on Jan–Oct 2025,
   test on Nov–Dec 2025. Random row splits leak future information into
   training through the lag/rolling features.
2. Start with **Isolation Forest** (unsupervised baseline) on the allowed
   feature set, then compare against a **supervised classifier** (Random
   Forest / XGBoost) using `anomaly_type` as a multi-class target, since
   you actually have labels here.
3. Use `weather_or_sensor` as a **second-stage classifier** once
   `anomaly_flag` fires — this two-stage structure (detect → classify
   cause) directly matches the problem statement's evaluation stress on
   distinguishing real weather from sensor faults.
4. Feature importance (built-in for Random Forest, or SHAP) on the trained
   model tells you which engineered features matter most — feed that
   directly into your dashboard's "evidence" breakdown (temporal/spatial/
   multivariate scores) for the explainability layer.

## Known limitations (stated up front, not discovered later)

- Climatology constants are reasonable approximations, not sourced from a
  verified official IMD climate-normals dataset — don't cite exact
  baseline numbers as authoritative without independent verification.
- 20 stations is a representative sample, not the real DES-AP network's
  actual density (2,800+ stations) — this is an intentional pilot-scale
  design choice, not an oversight.
- Real AWS sensor failure modes may be messier/more varied than the
  parametrized fault shapes here (real spikes aren't perfectly uniform
  random magnitude, real drift isn't perfectly linear) — good enough for
  MVP training, worth revisiting if real AP data becomes available for
  calibration.
- Station elevations are approximate, not survey-grade.
