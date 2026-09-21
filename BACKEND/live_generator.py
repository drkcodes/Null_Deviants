"""Backend-owned clean live telemetry generator."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "ML training" / "SIH26073_AP_AWS_observations.csv"
STATION_COUNT = 20
INTERVAL_MINUTES = 15


@dataclass(frozen=True)
class StationProfile:
    station_id: str
    temperature_mean: float
    humidity_mean: float
    pressure_mean: float


def _stable_noise(station_id: str, timestamp: datetime, channel: str, scale: float) -> float:
    key = f"{station_id}|{timestamp.isoformat()}|{channel}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    integer = int.from_bytes(digest[:8], "big")
    unit = integer / float(2**64 - 1)
    return (unit * 2.0 - 1.0) * scale


@lru_cache(maxsize=1)
def load_station_profiles() -> tuple[StationProfile, ...]:
    df = pd.read_csv(
        DATASET_PATH,
        usecols=[
            "station_id",
            "temperature_c",
            "relative_humidity_pct",
            "pressure_hpa",
        ],
    )
    profiles = []
    for station_id, group in df.groupby("station_id"):
        profiles.append(
            StationProfile(
                station_id=str(station_id),
                temperature_mean=float(group["temperature_c"].median()),
                humidity_mean=float(group["relative_humidity_pct"].median()),
                pressure_mean=float(group["pressure_hpa"].median()),
            )
        )
    profiles.sort(key=lambda profile: profile.station_id)
    if len(profiles) != STATION_COUNT:
        raise RuntimeError(
            f"Expected {STATION_COUNT} calibration profiles, found {len(profiles)}."
        )
    return tuple(profiles)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def generate_next_batch(
    states: dict[str, dict[str, float]],
    timestamp: datetime,
) -> tuple[list[dict], dict[str, dict[str, float]]]:
    """Generate one clean 20-station raw telemetry snapshot."""
    profiles = load_station_profiles()
    next_states: dict[str, dict[str, float]] = {}
    readings: list[dict] = []

    for profile in profiles:
        station_id = profile.station_id
        previous = states.get(station_id)
        if previous is None:
            raise RuntimeError(f"Missing clean generator state for {station_id}.")

        hour = timestamp.hour + timestamp.minute / 60.0
        diurnal = 2.0 * math.sin(2.0 * math.pi * (hour - 8.0) / 24.0)
        target_temperature = profile.temperature_mean + diurnal

        temperature = (
            float(previous["temperature_c"])
            + 0.08 * (target_temperature - float(previous["temperature_c"]))
            + _stable_noise(station_id, timestamp, "temperature", 0.08)
        )

        target_humidity = profile.humidity_mean - (
            temperature - profile.temperature_mean
        ) * 1.8

        humidity = (
            float(previous["relative_humidity_pct"])
            + 0.08 * (
                target_humidity - float(previous["relative_humidity_pct"])
            )
            + _stable_noise(station_id, timestamp, "humidity", 0.18)
        )

        pressure = (
            float(previous["pressure_hpa"])
            + 0.04 * (
                profile.pressure_mean - float(previous["pressure_hpa"])
            )
            + _stable_noise(station_id, timestamp, "pressure", 0.12)
        )

        next_state = {
            "temperature_c": _clamp(temperature, -20.0, 55.0),
            "relative_humidity_pct": _clamp(humidity, 0.0, 100.0),
            "pressure_hpa": _clamp(pressure, 850.0, 1100.0),
        }
        next_states[station_id] = next_state
        readings.append({
            "station_id": station_id,
            "timestamp": timestamp.isoformat(),
            "temperature_c": round(next_state["temperature_c"], 3),
            "relative_humidity_pct": round(next_state["relative_humidity_pct"], 3),
            "pressure_hpa": round(next_state["pressure_hpa"], 3),
        })

    return readings, next_states
