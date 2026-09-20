from __future__ import annotations

from dataclasses import dataclass


STATION_COUNT = 20


@dataclass(frozen=True)
class LiveScenario:
    scenario_id: str
    target_station_id: str
    intensity: int


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_scenario_id(scenario_id: str) -> str:
    aliases = {
        "scen-temp-spike": "temp_spike",
        "scen-temp-drop": "temp_drop",
        "scen-pressure-jump": "pressure_jump",
        "scen-press-jump": "pressure_jump",
        "scen-regional-heatwave": "regional_heatwave",
        "scen-heatwave": "regional_heatwave",
        "scen-regional-cold-spell": "regional_cold_spell",
        "scen-cold-spell": "regional_cold_spell",
    }

    scenario = aliases.get(str(scenario_id).strip())
    if scenario is None:
        supported = ", ".join(sorted(aliases))
        raise ValueError(
            f"Unsupported live scenario '{scenario_id}'. "
            f"Supported scenario IDs: {supported}"
        )

    return scenario


def intensity_scale(intensity: int) -> float:
    return clamp(float(intensity), 0.0, 100.0) / 100.0


def station_regions_from_rows(rows: list[dict]) -> dict[str, str]:
    regions = {}
    for row in rows:
        station_id = str(row.get("station_id", "")).strip()
        region = str(row.get("region", "")).strip()
        if station_id:
            regions[station_id] = region
    return regions


def validate_live_batch_baseline(readings: list[dict]) -> None:
    if len(readings) != STATION_COUNT:
        raise ValueError(
            f"Expected {STATION_COUNT} stations, found {len(readings)}."
        )

    station_ids = [
        str(reading.get("station_id", "")).strip()
        for reading in readings
    ]

    if len(set(station_ids)) != STATION_COUNT:
        raise ValueError("Live scenario baseline has duplicate stations.")

    timestamps = {
        str(reading.get("timestamp", "")).strip()
        for reading in readings
    }

    if len(timestamps) != 1:
        raise ValueError(
            "Live scenario baseline is not synchronized: "
            f"found {len(timestamps)} timestamps."
        )


def _target_station_ids(
    scenario: str,
    target_station_id: str,
    station_regions: dict[str, str],
) -> set[str]:
    target_station_id = target_station_id.strip()

    if scenario.startswith("regional_"):
        target_region = station_regions.get(target_station_id)
        if not target_region:
            raise ValueError(
                f"Cannot find region for station {target_station_id}."
            )

        return {
            station_id
            for station_id, region in station_regions.items()
            if region == target_region
        }

    return {target_station_id}


def apply_live_scenario(
    readings: list[dict],
    scenario_id: str,
    target_station_id: str,
    intensity: int,
    station_regions: dict[str, str],
) -> tuple[list[dict], dict]:
    validate_live_batch_baseline(readings)

    scenario = normalize_scenario_id(scenario_id)
    target_station_id = target_station_id.strip()
    station_ids = {
        str(reading.get("station_id", "")).strip()
        for reading in readings
    }

    if target_station_id not in station_ids:
        raise ValueError(
            f"Target station {target_station_id} is not present "
            "in the live fleet snapshot."
        )

    affected_stations = _target_station_ids(
        scenario,
        target_station_id,
        station_regions,
    )

    if not affected_stations:
        raise ValueError("Live scenario selected no affected stations.")

    scale = intensity_scale(intensity)
    updated: list[dict] = []

    for reading in readings:
        row = dict(reading)
        station_id = str(row["station_id"]).strip()

        if station_id in affected_stations:
            temperature = float(row["temperature_c"])
            humidity = float(row["relative_humidity_pct"])
            pressure = float(row["pressure_hpa"])

            if scenario == "temp_spike":
                temperature += 6.0 + 10.0 * scale
                humidity -= 4.0 * scale
            elif scenario == "temp_drop":
                temperature -= 6.0 + 10.0 * scale
                humidity += 5.0 * scale
            elif scenario == "pressure_jump":
                pressure += 10.0 + 18.0 * scale
            elif scenario == "regional_heatwave":
                temperature += 4.0 + 7.0 * scale
                humidity -= 6.0 * scale
                pressure -= 1.5 * scale
            elif scenario == "regional_cold_spell":
                temperature -= 4.0 + 7.0 * scale
                humidity += 5.0 * scale
                pressure += 1.5 * scale

            row["temperature_c"] = round(
                clamp(temperature, -20.0, 55.0),
                3,
            )
            row["relative_humidity_pct"] = round(
                clamp(humidity, 0.0, 100.0),
                3,
            )
            row["pressure_hpa"] = round(
                clamp(pressure, 850.0, 1100.0),
                3,
            )

        updated.append(row)

    return updated, {
        "scenario_id": scenario_id,
        "scenario": scenario,
        "target_station_id": target_station_id,
        "intensity": int(clamp(intensity, 0, 100)),
        "affected_station_ids": sorted(affected_stations),
        "affected_station_count": len(affected_stations),
    }
