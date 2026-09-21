"""Backend-owned clean live telemetry generator."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache


STATION_COUNT = 20
INTERVAL_MINUTES = 15


@dataclass(frozen=True)
class StationProfile:
    station_id: str
    temperature_mean: float
    humidity_mean: float
    pressure_mean: float


# Calibrated from the historical AWS observations stored in Neon.
# These are station-specific historical medians and are intentionally
# embedded so production inference does not depend on the training CSV.
_CALIBRATION_PROFILES = (
    StationProfile("AWS_AP01", 27.985000, 68.594000, 1003.879000),
    StationProfile("AWS_AP02", 28.362000, 72.742000, 1002.515000),
    StationProfile("AWS_AP03", 25.588000, 46.438000, 989.402000),
    StationProfile("AWS_AP04", 28.481000, 71.450000, 1003.404500),
    StationProfile("AWS_AP05", 28.119000, 37.528000, 974.249000),
    StationProfile("AWS_AP06", 26.870000, 68.882000, 1010.587000),
    StationProfile("AWS_AP07", 28.183000, 67.292000, 1008.731000),
    StationProfile("AWS_AP08", 25.930000, 45.442000, 993.267000),
    StationProfile("AWS_AP09", 27.871000, 41.541000, 965.223000),
    StationProfile("AWS_AP10", 29.332000, 66.846000, 1003.261000),
    StationProfile("AWS_AP11", 26.400000, 46.411000, 969.046000),
    StationProfile("AWS_AP12", 27.947000, 66.037000, 1006.151000),
    StationProfile("AWS_AP13", 28.485000, 67.394000, 1007.601000),
    StationProfile("AWS_AP14", 28.497000, 69.295000, 1006.524000),
    StationProfile("AWS_AP15", 29.821000, 66.083000, 1009.266000),
    StationProfile("AWS_AP16", 27.543000, 69.449000, 993.146000),
    StationProfile("AWS_AP17", 27.788000, 46.636000, 989.903000),
    StationProfile("AWS_AP18", 25.367000, 44.630000, 945.721000),
    StationProfile("AWS_AP19", 27.754000, 70.911000, 1007.875000),
    StationProfile("AWS_AP20", 23.699000, 43.829000, 935.755000),
)


def _stable_noise(
    station_id: str,
    timestamp: datetime,
    channel: str,
    scale: float,
) -> float:
    key = (
        f"{station_id}|{timestamp.isoformat()}|{channel}"
    ).encode("utf-8")

    digest = hashlib.sha256(key).digest()
    integer = int.from_bytes(digest[:8], "big")
    unit = integer / float(2**64 - 1)

    return (unit * 2.0 - 1.0) * scale


@lru_cache(maxsize=1)
def load_station_profiles() -> tuple[StationProfile, ...]:
    """Return the embedded production calibration profiles."""

    if len(_CALIBRATION_PROFILES) != STATION_COUNT:
        raise RuntimeError(
            f"Expected {STATION_COUNT} calibration profiles, "
            f"found {len(_CALIBRATION_PROFILES)}."
        )

    return _CALIBRATION_PROFILES


def _clamp(
    value: float,
    low: float,
    high: float,
) -> float:
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
            raise RuntimeError(
                f"Missing clean generator state for {station_id}."
            )

        hour = (
            timestamp.hour
            + timestamp.minute / 60.0
        )

        diurnal = (
            2.0
            * math.sin(
                2.0
                * math.pi
                * (hour - 8.0)
                / 24.0
            )
        )

        target_temperature = (
            profile.temperature_mean
            + diurnal
        )

        temperature = (
            float(previous["temperature_c"])
            + 0.08
            * (
                target_temperature
                - float(previous["temperature_c"])
            )
            + _stable_noise(
                station_id,
                timestamp,
                "temperature",
                0.08,
            )
        )

        target_humidity = (
            profile.humidity_mean
            - (
                temperature
                - profile.temperature_mean
            )
            * 1.8
        )

        humidity = (
            float(previous["relative_humidity_pct"])
            + 0.08
            * (
                target_humidity
                - float(previous["relative_humidity_pct"])
            )
            + _stable_noise(
                station_id,
                timestamp,
                "humidity",
                0.18,
            )
        )

        pressure = (
            float(previous["pressure_hpa"])
            + 0.04
            * (
                profile.pressure_mean
                - float(previous["pressure_hpa"])
            )
            + _stable_noise(
                station_id,
                timestamp,
                "pressure",
                0.12,
            )
        )

        next_state = {
            "temperature_c": _clamp(
                temperature,
                -20.0,
                55.0,
            ),
            "relative_humidity_pct": _clamp(
                humidity,
                0.0,
                100.0,
            ),
            "pressure_hpa": _clamp(
                pressure,
                850.0,
                1100.0,
            ),
        }

        next_states[station_id] = next_state

        readings.append(
            {
                "station_id": station_id,
                "timestamp": timestamp.isoformat(),
                "temperature_c": round(
                    next_state["temperature_c"],
                    3,
                ),
                "relative_humidity_pct": round(
                    next_state["relative_humidity_pct"],
                    3,
                ),
                "pressure_hpa": round(
                    next_state["pressure_hpa"],
                    3,
                ),
            }
        )

    return readings, next_states