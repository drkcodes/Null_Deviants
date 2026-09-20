"""
SkyGuardAI simulated live telemetry producer.

Normal operation:
    1. Read the latest live fleet state from the backend.
    2. Resume from that state.
    3. Generate the next 15-minute fleet snapshot.
    4. POST the complete snapshot to /ingest/batch.
    5. Repeat.

Important:
    - Does NOT write directly to PostgreSQL.
    - Does NOT modify the ML pipeline.
    - Uses the benchmark dataset only for station calibration/fallback.
    - Production timestamps are derived from the latest backend state.
"""

from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    PROJECT_ROOT
    / "ML training"
    / "SIH26073_AP_AWS_observations.csv"
)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"

INTERVAL_MINUTES = 15
STATION_COUNT = 20


@dataclass
class StationProfile:
    station_id: str
    temperature_mean: float
    temperature_std: float
    humidity_mean: float
    humidity_std: float
    pressure_mean: float
    pressure_std: float


@dataclass
class StationState:
    temperature: float
    humidity: float
    pressure: float


def load_station_profiles() -> list[StationProfile]:
    print(f"Loading calibration data: {DATASET_PATH}")

    df = pd.read_csv(
        DATASET_PATH,
        usecols=[
            "station_id",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ],
    )

    profiles: list[StationProfile] = []

    for station_id, group in df.groupby("station_id"):
        profiles.append(
            StationProfile(
                station_id=station_id,
                temperature_mean=float(
                    group["temperature_c"].median()
                ),
                temperature_std=float(
                    group["temperature_c"].std()
                ),
                humidity_mean=float(
                    group["relative_humidity_pct"].median()
                ),
                humidity_std=float(
                    group["relative_humidity_pct"].std()
                ),
                pressure_mean=float(
                    group["pressure_hpa"].median()
                ),
                pressure_std=float(
                    group["pressure_hpa"].std()
                ),
            )
        )

    profiles.sort(key=lambda profile: profile.station_id)

    if len(profiles) != STATION_COUNT:
        raise RuntimeError(
            f"Expected {STATION_COUNT} stations, "
            f"found {len(profiles)}"
        )

    return profiles


def initialize_states_from_profiles(
    profiles: list[StationProfile],
    rng: random.Random,
) -> dict[str, StationState]:
    states: dict[str, StationState] = {}

    for profile in profiles:
        states[profile.station_id] = StationState(
            temperature=profile.temperature_mean
            + rng.uniform(-0.5, 0.5),
            humidity=profile.humidity_mean
            + rng.uniform(-1.0, 1.0),
            pressure=profile.pressure_mean
            + rng.uniform(-0.5, 0.5),
        )

    return states


def initialize_states_from_latest(
    latest_rows: list[dict],
) -> tuple[dict[str, StationState], datetime]:
    if not latest_rows:
        raise RuntimeError("Backend returned no live stations")

    states: dict[str, StationState] = {}
    timestamps: set[datetime] = set()

    for row in latest_rows:
        station_id = str(row["station_id"])

        timestamp = pd.to_datetime(
            row["timestamp"],
            utc=True,
        ).to_pydatetime()

        timestamps.add(timestamp)

        states[station_id] = StationState(
            temperature=float(row["temperature_c"]),
            humidity=float(row["relative_humidity_pct"]),
            pressure=float(row["pressure_hpa"]),
        )

    if len(states) != STATION_COUNT:
        raise RuntimeError(
            f"Expected {STATION_COUNT} live stations, "
            f"found {len(states)}"
        )

    if len(timestamps) != 1:
        raise RuntimeError(
            "Latest live fleet is not synchronized: "
            f"found {len(timestamps)} timestamps"
        )

    latest_timestamp = next(iter(timestamps))

    return states, latest_timestamp


def fetch_latest_live_state(
    backend_url: str,
) -> tuple[dict[str, StationState], datetime]:
    url = backend_url.rstrip("/") + "/stations/latest"

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        raise RuntimeError(
            "Expected /stations/latest to return a list"
        )

    return initialize_states_from_latest(payload)


def clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    return max(low, min(high, value))


def generate_next_state(
    profile: StationProfile,
    state: StationState,
    timestamp: datetime,
    rng: random.Random,
) -> StationState:
    """
    Generate a temporally continuous normal-weather state.

    The transition is intentionally small relative to the anomaly
    magnitudes present in the benchmark dataset.
    """

    hour = timestamp.hour + timestamp.minute / 60.0

    diurnal = 2.0 * math.sin(
        2.0 * math.pi * (hour - 8.0) / 24.0
    )

    target_temperature = (
        profile.temperature_mean + diurnal
    )

    temperature = (
        state.temperature
        + 0.08
        * (target_temperature - state.temperature)
        + rng.gauss(0.0, 0.08)
    )

    target_humidity = (
        profile.humidity_mean
        - (temperature - profile.temperature_mean) * 1.8
    )

    humidity = (
        state.humidity
        + 0.08
        * (target_humidity - state.humidity)
        + rng.gauss(0.0, 0.18)
    )

    target_pressure = profile.pressure_mean

    pressure = (
        state.pressure
        + 0.04
        * (target_pressure - state.pressure)
        + rng.gauss(0.0, 0.12)
    )

    return StationState(
        temperature=clamp(
            temperature,
            -20.0,
            55.0,
        ),
        humidity=clamp(
            humidity,
            0.0,
            100.0,
        ),
        pressure=clamp(
            pressure,
            850.0,
            1100.0,
        ),
    )


def build_batch(
    profiles: list[StationProfile],
    states: dict[str, StationState],
    timestamp: datetime,
    rng: random.Random,
) -> list[dict]:
    readings: list[dict] = []

    for profile in profiles:
        current = states[profile.station_id]

        next_state = generate_next_state(
            profile,
            current,
            timestamp,
            rng,
        )

        states[profile.station_id] = next_state

        readings.append(
            {
                "station_id": profile.station_id,
                "timestamp": timestamp.isoformat(),
                "temperature_c": round(
                    next_state.temperature,
                    3,
                ),
                "relative_humidity_pct": round(
                    next_state.humidity,
                    3,
                ),
                "pressure_hpa": round(
                    next_state.pressure,
                    3,
                ),
            }
        )

    return readings


def print_batch(
    readings: list[dict],
) -> None:
    print()
    print("=" * 72)
    print(
        f"TIMESTAMP: {readings[0]['timestamp']}"
    )
    print(
        f"STATIONS: {len(readings)}"
    )
    print("=" * 72)

    for reading in readings:
        print(
            f"{reading['station_id']} | "
            f"T={reading['temperature_c']:7.3f} | "
            f"RH={reading['relative_humidity_pct']:7.3f} | "
            f"P={reading['pressure_hpa']:8.3f}"
        )


def send_batch(
    backend_url: str,
    readings: list[dict],
) -> dict:
    url = backend_url.rstrip("/") + "/ingest/batch"

    response = requests.post(
        url,
        json={"readings": readings},
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def validate_batch_timestamp(
    timestamp: datetime,
    latest_timestamp: datetime,
) -> None:
    expected = (
        latest_timestamp
        + timedelta(minutes=INTERVAL_MINUTES)
    )

    if timestamp != expected:
        raise RuntimeError(
            "Telemetry timestamp continuity violation: "
            f"expected {expected.isoformat()}, "
            f"got {timestamp.isoformat()}"
        )


def parse_start_timestamp(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    parsed = pd.to_datetime(
        value,
        utc=True,
    )

    if pd.isna(parsed):
        raise ValueError(
            f"Invalid --start-time: {value}"
        )

    return parsed.to_pydatetime()


def align_to_15_minutes(
    timestamp: datetime,
) -> datetime:
    timestamp = timestamp.astimezone(timezone.utc)

    return timestamp.replace(
        minute=(timestamp.minute // INTERVAL_MINUTES)
        * INTERVAL_MINUTES,
        second=0,
        microsecond=0,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "SkyGuardAI simulated live AWS telemetry producer"
        )
    )

    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND_URL,
        help="FastAPI backend base URL",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=INTERVAL_MINUTES,
        help=(
            "Real-time sleep interval in minutes. "
            "Production should use 15."
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate and send exactly one batch",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Generate telemetry without sending it. "
            "Requires --start-time."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=26073,
        help="Deterministic generator seed",
    )

    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        help=(
            "Explicit UTC start timestamp for accelerated tests. "
            "Example: 2026-09-20T05:45:00Z"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.interval <= 0:
        raise ValueError(
            "Interval must be greater than zero"
        )

    rng = random.Random(args.seed)

    profiles = load_station_profiles()
    profile_by_station = {
        profile.station_id: profile
        for profile in profiles
    }

    explicit_start = parse_start_timestamp(
        args.start_time
    )

    if explicit_start is not None:
        states = initialize_states_from_profiles(
            profiles,
            rng,
        )

        latest_timestamp = explicit_start

        print(
            "Using explicit test start timestamp:"
            f" {latest_timestamp.isoformat()}"
        )

    else:
        states, latest_timestamp = fetch_latest_live_state(
            args.backend
        )

        print(
            "Resuming from backend live state:"
            f" {latest_timestamp.isoformat()}"
        )

    if set(states) != set(profile_by_station):
        raise RuntimeError(
            "Station set mismatch between calibration "
            "profiles and live state"
        )

    print()
    print("SkyGuardAI LIVE TELEMETRY PRODUCER")
    print("-" * 72)
    print(f"Stations       : {len(profiles)}")
    print(f"Interval       : {args.interval} minutes")
    print(f"Backend        : {args.backend}")
    print(f"Dry run        : {args.dry_run}")
    print(f"Seed           : {args.seed}")
    print(f"Dataset        : {DATASET_PATH}")
    print()

    if args.dry_run and explicit_start is None:
        raise ValueError(
            "--dry-run requires --start-time so it "
            "cannot accidentally query production state "
            "and look like a live run."
        )

    if explicit_start is not None:
        next_timestamp = explicit_start
    else:
        next_timestamp = (
            latest_timestamp
            + timedelta(minutes=INTERVAL_MINUTES)
        )

    while True:
        if not args.dry_run and explicit_start is None:
            validate_batch_timestamp(
                next_timestamp,
                latest_timestamp,
            )

        readings = build_batch(
            profiles,
            states,
            next_timestamp,
            rng,
        )

        print_batch(readings)

        if args.dry_run:
            print("\nDRY RUN: batch was not sent.")

        else:
            try:
                result = send_batch(
                    args.backend,
                    readings,
                )

                print("\nINGESTION SUCCESS")
                print(
                    "stations_processed="
                    f"{result.get('stations_processed')}"
                )

            except requests.RequestException as exc:
                print(
                    "\nINGESTION ERROR:"
                    f" {exc}"
                )
                raise

        latest_timestamp = next_timestamp

        if args.once:
            break

        next_timestamp = (
            latest_timestamp
            + timedelta(minutes=args.interval)
        )

        print(
            f"\nNext batch in {args.interval} minute(s)..."
        )

        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()