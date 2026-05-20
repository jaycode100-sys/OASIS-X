"""
ncc_feed.py
-----------
NCC (Nigerian Communications Commission) baseline parameters and live-feed
drift simulator.

Provides:
  - NCC QoS thresholds from published reports
  - Per-city network baseline profiles
  - simulate_ncc_drift(): adjusts a telemetry DataFrame to mimic live NCC
    feed parameter drift over time
"""

import numpy as np
import pandas as pd
from datetime import datetime


# ── NCC Published QoS Thresholds ──────────────────────────────────────────────
# Source: NCC Quality of Service Regulations & Annual Reports

NCC_QOS_THRESHOLDS = {
    "latency_ms":       {"max": 150,    "target": 25,   "unit": "ms"},
    "packet_loss_pct":  {"max": 1.0,    "target": 0.2,  "unit": "%"},
    "osnr_db":          {"min": 15.0,   "target": 20.0, "unit": "dB"},
    "ber":              {"max": 1e-5,   "target": 1e-7, "unit": ""},
    "availability_pct": {"min": 99.0,   "target": 99.9, "unit": "%"},
}


# ── City Baseline Profiles ─────────────────────────────────────────────────────
# Reflects real-world differences in Nigerian city network infrastructure.

NCC_CITY_PROFILES = {
    "Lagos": {
        "description": "High density, coastal humidity, most congested backbone",
        "osnr_db":     20.5,
        "latency_ms":  12.0,
        "ber":         8e-7,
        "power_dbm":   -1.5,
        "availability_pct": 99.1,
        "peak_hours":  [19, 20, 21, 22],
        "peak_latency_multiplier": 1.6,
        "generator_failure_risk": 0.12,   # probability per day
    },
    "Abuja": {
        "description": "FCT backbone, relatively stable, government infrastructure",
        "osnr_db":     21.0,
        "latency_ms":  11.0,
        "ber":         5e-7,
        "power_dbm":   -1.0,
        "availability_pct": 99.4,
        "peak_hours":  [8, 9, 18, 19],
        "peak_latency_multiplier": 1.3,
        "generator_failure_risk": 0.07,
    },
    "PortHarcourt": {
        "description": "Oil & gas hub, high humidity, frequent rain attenuation",
        "osnr_db":     20.2,
        "latency_ms":  14.0,
        "ber":         1.2e-6,
        "power_dbm":   -2.0,
        "availability_pct": 98.8,
        "peak_hours":  [18, 19, 20, 21],
        "peak_latency_multiplier": 1.4,
        "generator_failure_risk": 0.15,
    },
    "Kano": {
        "description": "Northern hub, worst harmattan exposure, lower population density",
        "osnr_db":     19.8,
        "latency_ms":  16.0,
        "ber":         1.5e-6,
        "power_dbm":   -2.5,
        "availability_pct": 98.5,
        "peak_hours":  [20, 21, 22],
        "peak_latency_multiplier": 1.2,
        "generator_failure_risk": 0.18,
    },
}


def get_ncc_baseline(city: str = "Lagos") -> dict:
    """
    Return NCC baseline parameters and QoS thresholds for the given city.

    Args:
        city: One of 'Lagos', 'Abuja', 'PortHarcourt', 'Kano'.

    Returns:
        Dict with baseline metrics, QoS thresholds, and city description.
    """
    profile = NCC_CITY_PROFILES.get(city, NCC_CITY_PROFILES["Lagos"])
    return {
        "city": city,
        "description": profile["description"],
        "baselines": {
            "osnr_db":          profile["osnr_db"],
            "latency_ms":       profile["latency_ms"],
            "ber":              profile["ber"],
            "power_dbm":        profile["power_dbm"],
            "availability_pct": profile["availability_pct"],
        },
        "ncc_thresholds": NCC_QOS_THRESHOLDS,
        "risk_factors": {
            "peak_hours":               profile["peak_hours"],
            "peak_latency_multiplier":  profile["peak_latency_multiplier"],
            "generator_failure_risk":   profile["generator_failure_risk"],
        },
    }


def get_current_season() -> str:
    """
    Infer the current Nigerian environmental season from the current month.

    Seasons:
      - harmattan: November – February
      - rainy:     April – October
      - dry:       March (transition)
      - normal:    default fallback
    """
    month = datetime.now().month
    if month in (11, 12, 1, 2):
        return "harmattan"
    elif month in range(4, 11):
        return "rainy"
    elif month == 3:
        return "dry"
    return "normal"


def simulate_ncc_drift(df: pd.DataFrame, city: str = "Lagos", drift_seed: int = 7) -> pd.DataFrame:
    """
    Apply NCC-realistic parameter drift to a telemetry DataFrame.

    Simulates the kind of gradual, real-world variation that would be observed
    in a live NCC feed — slow OSNR drift, latency variance, and micro BER
    fluctuations driven by infrastructure aging and load.

    Args:
        df:         Telemetry DataFrame (must contain osnr_db, latency_ms, ber).
        city:       City profile to use for drift magnitude.
        drift_seed: Seed for reproducible drift generation.

    Returns:
        Copy of the DataFrame with drift applied and a new 'ncc_drift_applied'
        column set to True.
    """
    rng = np.random.default_rng(drift_seed)
    profile = NCC_CITY_PROFILES.get(city, NCC_CITY_PROFILES["Lagos"])
    df = df.copy()
    n = len(df)

    # Slow sinusoidal OSNR drift (infrastructure aging + temperature cycling)
    osnr_drift = 0.4 * np.sin(np.linspace(0, 2 * np.pi, n)) + rng.normal(0, 0.1, n)

    # Latency drift driven by backbone congestion fluctuations
    latency_drift = (profile["peak_latency_multiplier"] - 1.0) * 3.0 * np.abs(
        np.sin(np.linspace(0, 3 * np.pi, n))
    ) + rng.normal(0, 0.5, n)

    # BER micro-fluctuations (amplifier noise, connector wear)
    ber_drift_mult = 1.0 + rng.uniform(-0.05, 0.15, n)

    df["osnr_db"] = np.round(df["osnr_db"] + osnr_drift, 3)
    df["latency_ms"] = np.round((df["latency_ms"] + latency_drift).clip(lower=5.0), 3)
    df["ber"] = (df["ber"] * ber_drift_mult).clip(lower=0)
    df["ncc_drift_applied"] = True

    return df


def evaluate_against_ncc(df: pd.DataFrame) -> dict:
    """
    Evaluate a telemetry DataFrame against NCC QoS thresholds.

    Returns a compliance report showing what percentage of readings meet
    each NCC threshold.

    Args:
        df: Processed telemetry DataFrame.

    Returns:
        Dict with per-metric compliance percentages and overall status.
    """
    n = len(df)
    report = {}

    if "latency_ms" in df.columns:
        threshold = NCC_QOS_THRESHOLDS["latency_ms"]["max"]
        pct = (df["latency_ms"] <= threshold).sum() / n * 100
        report["latency_compliance_pct"] = round(pct, 2)

    if "osnr_db" in df.columns:
        threshold = NCC_QOS_THRESHOLDS["osnr_db"]["min"]
        pct = (df["osnr_db"] >= threshold).sum() / n * 100
        report["osnr_compliance_pct"] = round(pct, 2)

    if "ber" in df.columns:
        threshold = NCC_QOS_THRESHOLDS["ber"]["max"]
        pct = (df["ber"] <= threshold).sum() / n * 100
        report["ber_compliance_pct"] = round(pct, 2)

    overall = all(v >= 80.0 for v in report.values())
    report["overall_status"] = "COMPLIANT" if overall else "NON_COMPLIANT"

    return report
