"""
SIH26073 Phase 8 — Deterministic degradation and maintenance-risk engine.

This module is intentionally independent of the Phase 7 health implementation.
It consumes Phase 7 health snapshots and persisted live anomaly rows and
produces an operational maintenance-risk INDEX. It is not a failure model,
survival model, RUL model, or probability estimate.
"""

from __future__ import annotations

from typing import Any, Iterable
import math
import pandas as pd


ENGINE_VERSION = "deterministic_maintenance_risk_v1"

GROUP_WEIGHTS = {
    "progressive_calibration": 0.30,
    "hard_fault": 0.25,
    "isolation": 0.15,
    "sensor_burden": 0.20,
    "communications_data": 0.10,
}


def clip01(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _as_timestamp(value: Any) -> pd.Timestamp | None:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("Asia/Kolkata")
    return ts


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _confidence_for_sufficiency(health: dict) -> str:
    sufficiency = health.get("data_sufficiency") or {}
    status = str(sufficiency.get("status", "insufficient")).lower()
    samples = int(max(0, round(_finite(sufficiency.get("samples_used"), 0))))
    if status == "insufficient" or samples < 8:
        return "none"
    if status == "low" or samples < 24:
        return "low"
    if status == "medium" or samples < 96:
        return "medium"
    return "high"


def _group_a(health: dict) -> tuple[float, list[str]]:
    drift = health.get("drift") or {}
    p = clip01(drift.get("progressive"))
    s = clip01(drift.get("persistence"))
    r = clip01(_finite(drift.get("run_length"), 0.0) / 5.0)
    d = clip01(drift.get("directional_consistency"))

    if p < 0.25 and s < 0.50 and r < 0.40:
        return 0.0, []

    value = clip01(0.45 * p + 0.25 * s + 0.15 * r + 0.15 * d)

    drivers = []
    if p >= 0.25:
        drivers.append("Progressive degradation evidence")
    if s >= 0.50:
        drivers.append("Persistent drift")
    if r >= 0.40:
        drivers.append("Repeated directional drift observations")
    if d >= 0.70:
        drivers.append("High directional consistency")
    return value, drivers


def _group_b(health: dict) -> tuple[float, list[str]]:
    fault = health.get("sensor_fault") or {}
    frozen = clip01(fault.get("frozen"))
    physical = clip01(fault.get("physical_consistency"))
    value = max(frozen, physical)

    drivers = []
    if frozen >= 0.70:
        drivers.append("Frozen/stuck sensor evidence")
    if physical >= 1.0:
        drivers.append("Physical-consistency violation")
    return value, drivers


def _group_c(health: dict) -> tuple[float, list[str]]:
    fault = health.get("sensor_fault") or {}
    value = clip01(fault.get("isolation"))
    drivers = []
    if value >= 0.50:
        drivers.append("Station is isolated from contemporaneous neighbor movement")
    return value, drivers


def _sensor_anomaly_count_7d(
    anomaly_rows: Iterable[dict] | None,
    now_ts: pd.Timestamp,
) -> int:
    cutoff = now_ts - pd.Timedelta(days=7)
    count = 0

    for row in anomaly_rows or []:
        if not isinstance(row, dict):
            continue
        timestamp = _as_timestamp(row.get("timestamp"))
        if timestamp is None or timestamp < cutoff:
            continue

        try:
            anomaly = int(row.get("anomaly", 1))
        except (TypeError, ValueError):
            anomaly = 1

        # get_live_anomaly_history normally returns only anomaly=1 rows,
        # but retain the explicit check for evaluator-owned inputs.
        if anomaly != 1:
            continue

        cause = str(row.get("weather_or_sensor") or "").strip().lower()
        if cause == "sensor":
            count += 1

    return count


def _group_d(
    anomaly_rows: Iterable[dict] | None,
    now_ts: pd.Timestamp,
) -> tuple[float, list[str], int]:
    count = _sensor_anomaly_count_7d(anomaly_rows, now_ts)
    value = clip01(count / 8.0)
    drivers = (
        [f"{count} sensor-attributed live anomalies in the last 7 days."]
        if count > 0
        else []
    )
    return value, drivers, count


def _group_e(health: dict) -> tuple[float, list[str]]:
    quality = health.get("data_quality") or {}
    missing_rate = clip01(quality.get("missing_rate"))
    timestamp_gap = clip01(quality.get("timestamp_gap"))
    age_term = clip01(_finite(quality.get("observation_age_seconds"), 0.0) / 21600.0)

    value = clip01(
        0.50 * missing_rate
        + 0.25 * timestamp_gap
        + 0.25 * age_term
    )

    drivers = []
    if missing_rate > 0:
        drivers.append("Missing telemetry is contributing to maintenance attention.")
    if timestamp_gap > 0:
        drivers.append("Timestamp gap is contributing to maintenance attention.")
    if age_term > 0:
        drivers.append("Observation age is contributing to maintenance attention.")
    return value, drivers


def _priority_from_risk(risk: int | None) -> str:
    if risk is None:
        return "Insufficient Data"
    if risk <= 24:
        return "Monitor"
    if risk <= 49:
        return "Attention"
    if risk <= 74:
        return "Elevated"
    return "Priority"


def _risk_status(risk: int | None) -> str:
    if risk is None:
        return "Insufficient Data"
    return _priority_from_risk(risk)


def _recommended_action(
    a: float,
    b: float,
    e: float,
    priority: str,
    quality: dict,
) -> str:
    """
    Closed action set from the Phase 8 specification.
    """
    missing = clip01(quality.get("missing_rate"))
    gap = clip01(quality.get("timestamp_gap"))
    age = _finite(quality.get("observation_age_seconds"), 0.0)

    if e >= 0.50 and e > a and e > b:
        return "Review data quality"

    if (
        (gap > 0 or age >= 21600.0)
        and e > a
        and e > b
        and a < 0.40
        and b < 0.40
    ):
        return "Investigate communications"

    if b >= 0.70:
        return "Inspect sensor"

    if a >= 0.50 or (priority in {"Elevated", "Priority"} and a >= b):
        return "Calibrate / inspect"

    if e >= 0.50 and missing > 0:
        return "Review data quality"

    return "Monitor"


def _trajectory_from_anchors(
    current_risk: int | None,
    anchors: dict[str, dict | None],
) -> dict:
    """
    Compute trajectory using only sparse health anchors:
    T, T-6h, T-24h, T-7d.

    Anchor values are already produced by Phase 7; this function never
    recalculates or modifies the Phase 7 health formula.
    """
    if current_risk is None:
        return {
            "status": "unknown",
            "direction": "unknown",
            "delta_risk": None,
            "slope_per_hour": None,
            "reference_window": None,
            "elevated_duration": None,
            "recovery_detected": False,
        }

    anchor_24 = anchors.get("24h")
    anchor_6 = anchors.get("6h")
    anchor_7d = anchors.get("7d")

    risk_24 = None if not anchor_24 else anchor_24.get("maintenance_risk")
    risk_6 = None if not anchor_6 else anchor_6.get("maintenance_risk")
    risk_7d = None if not anchor_7d else anchor_7d.get("maintenance_risk")

    reference_risk = None
    reference_window = None
    hours = None

    if risk_24 is not None:
        reference_risk = int(risk_24)
        reference_window = "24h"
        hours = 24
    elif risk_6 is not None:
        reference_risk = int(risk_6)
        reference_window = "6h"
        hours = 6

    if reference_risk is None:
        direction = "stable"
        delta = None
        slope = None
    else:
        delta = int(current_risk) - reference_risk
        slope = float(delta) / float(hours)
        if delta >= 8:
            direction = "worsening"
        elif delta <= -8:
            direction = "improving"
        else:
            direction = "stable"

    # Duration is deliberately anchor-based; never claim exact 15-minute
    # duration from these sparse points.
    current_elevated = current_risk >= 25
    if not current_elevated:
        elevated_duration = "none"
    elif risk_6 is not None and int(risk_6) >= 25:
        if risk_24 is not None and int(risk_24) >= 25:
            if risk_7d is not None and int(risk_7d) >= 25:
                elevated_duration = ">=7d"
            else:
                elevated_duration = ">=24h"
        else:
            elevated_duration = ">=6h"
    else:
        elevated_duration = "<6h"

    recovery = direction == "improving"

    return {
        "status": "computed",
        "direction": direction,
        "delta_risk": delta,
        "slope_per_hour": round(slope, 4) if slope is not None else None,
        "reference_window": reference_window,
        "elevated_duration": elevated_duration,
        "recovery_detected": recovery,
    }


def _attention_horizon(
    risk: int,
    confidence: str,
    trajectory: dict,
) -> dict | None:
    if (
        trajectory.get("direction") != "worsening"
        or confidence not in {"medium", "high"}
        or risk >= 75
    ):
        return None

    slope = _finite(trajectory.get("slope_per_hour"), 0.0)
    if slope <= 0:
        return None

    hours = (75.0 - float(risk)) / slope
    if not 1.0 <= hours <= 72.0:
        return None

    return {
        "hours": round(hours, 1),
        "basis": "Linear continuation of the recent maintenance-risk trend.",
        "disclaimer": (
            "Trend estimate only; not a failure forecast or remaining useful life."
        ),
    }


def risk_from_health(
    health_dict: dict,
    anomaly_rows: Iterable[dict] | None,
    now_ts: Any,
) -> dict:
    """
    Calculate the current Phase 8 index from one frozen Phase 7 health
    snapshot. No trajectory is calculated here.
    """
    now = _as_timestamp(now_ts)
    if now is None:
        now = _as_timestamp(health_dict.get("timestamp"))

    confidence = _confidence_for_sufficiency(health_dict)
    sufficiency = health_dict.get("data_sufficiency") or {}
    samples = int(max(0, round(_finite(sufficiency.get("samples_used"), 0))))

    if (
        confidence == "none"
        or samples < 8
        or (health_dict.get("overall") or {}).get("score") is None
    ):
        return {
            "maintenance_risk": None,
            "priority": "Insufficient Data",
            "confidence": "none",
            "action_queue": "none",
            "recommended_action": "Monitor",
            "drivers": ["Insufficient telemetry history for maintenance prioritization."],
            "groups": {
                "A_progressive_calibration": 0.0,
                "B_hard_fault": 0.0,
                "C_isolation": 0.0,
                "D_sensor_burden_7d": 0.0,
                "E_communications_data": 0.0,
            },
            "sensor_anomaly_count_7d": 0,
            "weather_suppression_applied": False,
            "engine_version": ENGINE_VERSION,
        }

    if now is None:
        raise ValueError("A valid now_ts or health timestamp is required.")

    a, a_drivers = _group_a(health_dict)
    b, b_drivers = _group_b(health_dict)
    c, c_drivers = _group_c(health_dict)
    d, d_drivers, sensor_count = _group_d(anomaly_rows, now)
    e, e_drivers = _group_e(health_dict)

    network = health_dict.get("network") or {}
    coherence = clip01(network.get("coherence"))

    suppression_applied = False
    if coherence >= 0.70 and c < 0.50:
        a = 0.40 * a
        suppression_applied = True

    p = clip01(
        0.30 * a
        + 0.25 * b
        + 0.15 * c
        + 0.20 * d
        + 0.10 * e
    )

    risk = int(round(100.0 * p))

    if confidence == "low":
        risk = min(risk, 49)

    priority = _priority_from_risk(risk)

    quality = health_dict.get("data_quality") or {}
    action = _recommended_action(a, b, e, priority, quality)

    drivers = []
    for group_drivers in (a_drivers, b_drivers, c_drivers, d_drivers, e_drivers):
        for driver in group_drivers:
            if driver not in drivers:
                drivers.append(driver)

    if suppression_applied:
        drivers.append(
            "Regional network coherence reduced calibration-risk weight; this is not treated as fleet sensor failure."
        )

    if priority in {"Monitor", "Attention"} and all(
        value < 0.20 for value in (a, b, c, d, e)
    ) and risk < 25:
        drivers = ["No elevated maintenance-risk signal was observed."]

    action_queue = (
        "communications"
        if action in {"Review data quality", "Investigate communications"}
        else "sensor"
        if action in {"Inspect sensor", "Calibrate / inspect"}
        else "monitor"
    )

    return {
        "maintenance_risk": risk,
        "priority": priority,
        "confidence": confidence,
        "action_queue": action_queue,
        "recommended_action": action,
        "drivers": drivers[:5],
        "groups": {
            "A_progressive_calibration": round(a, 4),
            "B_hard_fault": round(b, 4),
            "C_isolation": round(c, 4),
            "D_sensor_burden_7d": round(d, 4),
            "E_communications_data": round(e, 4),
        },
        "sensor_anomaly_count_7d": sensor_count,
        "weather_suppression_applied": suppression_applied,
        "engine_version": ENGINE_VERSION,
    }


def attach_trajectory_and_horizon(
    current: dict,
    anchors: dict[str, dict | None],
) -> dict:
    result = dict(current)
    trajectory = _trajectory_from_anchors(
        current.get("maintenance_risk"),
        anchors,
    )
    result["trajectory"] = trajectory
    result["attention_horizon"] = _attention_horizon(
        current.get("maintenance_risk"),
        current.get("confidence", "none"),
        trajectory,
    )
    return result


def rank_maintenance_results(results: list[dict]) -> list[dict]:
    """
    Deterministic fleet ordering.

    Ranked:
      risk != null and confidence != none

    Tie-breakers:
      1. maintenance risk DESC
      2. hard-fault group B DESC
      3. sensor-burden group D DESC
      4. confidence high > medium > low
      5. station_id ASC

    Insufficient results are appended afterward, station_id ASC.
    """
    confidence_order = {"high": 3, "medium": 2, "low": 1, "none": 0}

    ranked = [
        result
        for result in results
        if result.get("maintenance_risk") is not None
        and result.get("confidence") != "none"
    ]
    unranked = [
        result
        for result in results
        if result.get("maintenance_risk") is None
        or result.get("confidence") == "none"
    ]

    ranked.sort(
        key=lambda result: (
            -int(result.get("maintenance_risk", 0)),
            -float((result.get("groups") or {}).get("B_hard_fault", 0.0)),
            -float((result.get("groups") or {}).get("D_sensor_burden_7d", 0.0)),
            -confidence_order.get(str(result.get("confidence", "none")), 0),
            str(result.get("station_id", "")),
        )
    )

    for index, result in enumerate(ranked, start=1):
        result["priority_rank"] = index

    unranked.sort(key=lambda result: str(result.get("station_id", "")))
    for result in unranked:
        result["priority_rank"] = None

    return ranked + unranked
