import numpy as np
import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────
BASELINE_OSNR_DB = 22.0       # Expected OSNR for a healthy fibre span (dB)
CRITICAL_OSNR_DB = 15.0       # Below this → CRITICAL state
DEGRADING_OSNR_DB = 19.0      # Below this → DEGRADING state
CRITICAL_BER = 1e-5           # Above this → CRITICAL state
SAFE_RISK_SCORE = 0.3         # Risk score threshold for auto-approving DEGRADING actions


# ── State Classification ───────────────────────────────────────────────────────

def classify_state(row) -> str:
    """Classify a single telemetry row's network health state."""
    if row["osnr_db"] < CRITICAL_OSNR_DB or row["ber"] > CRITICAL_BER:
        return "CRITICAL"
    if row["osnr_db"] < DEGRADING_OSNR_DB or row.get("anomaly_flag", 0) == 1:
        return "DEGRADING"
    return "NORMAL"


def decide_action(row) -> str:
    """Decide the healing action for a single telemetry row."""
    state = row.get("state", classify_state(row))
    if state == "CRITICAL":
        return "IMMEDIATE_REROUTE_TO_PROTECTION_PATH"
    if state == "DEGRADING":
        return "ADJUST_AMPLIFIER_GAIN_AND_MONITOR"
    return "NO_ACTION"


# ── Batch Decision Processing (vectorized) ────────────────────────────────────

def process_decisions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich a telemetry DataFrame with risk scores, state classifications,
    and recommended healing actions.

    Uses vectorized NumPy operations for performance — avoids slow row-wise
    .apply() calls.

    Returns a copy of the DataFrame with added columns:
        osnr_drop, ber_rise, risk_score, state, recommended_action
    """
    df = df.copy()

    # Trend features
    df["osnr_drop"] = df["osnr_db"].diff().fillna(0)
    df["ber_rise"] = df["ber"].diff().fillna(0)

    # Risk score: higher latency × larger OSNR deficit = higher risk
    df["risk_score"] = (df["latency_ms"] * (BASELINE_OSNR_DB - df["osnr_db"])).clip(lower=0)

    # Anomaly flag column may not exist if detector wasn't run
    anomaly = df["anomaly_flag"] if "anomaly_flag" in df.columns else 0

    # Vectorized state classification
    critical_mask = (df["osnr_db"] < CRITICAL_OSNR_DB) | (df["ber"] > CRITICAL_BER)
    degrading_mask = (df["osnr_db"] < DEGRADING_OSNR_DB) | (anomaly == 1)

    df["state"] = np.select(
        [critical_mask, degrading_mask],
        ["CRITICAL", "DEGRADING"],
        default="NORMAL",
    )

    # Vectorized action assignment
    df["recommended_action"] = np.select(
        [df["state"] == "CRITICAL", df["state"] == "DEGRADING"],
        ["IMMEDIATE_REROUTE_TO_PROTECTION_PATH", "ADJUST_AMPLIFIER_GAIN_AND_MONITOR"],
        default="NO_ACTION",
    )

    return df


# ── Safety / Validation Layer ──────────────────────────────────────────────────

def validate_and_execute(data: dict, simulation_result: dict) -> str:
    """
    Validates a proposed healing action against simulation feedback before
    committing to execution.

    Args:
        data:              A single telemetry row as a dict (must contain
                           'state' and 'recommended_action').
        simulation_result: Simulation output dict with keys 'status' and
                           'risk_score'.

    Returns:
        Human-readable string describing the outcome.
    """
    action = data.get("recommended_action", "NO_ACTION")
    state = data.get("state", "NORMAL")

    sim_status = simulation_result.get("status")
    risk_score = simulation_result.get("risk_score", 0)

    if state == "NORMAL":
        return "No action needed — network operating normally."

    if state == "DEGRADING":
        if sim_status == "safe" and risk_score < SAFE_RISK_SCORE:
            return f"Preventive action approved: {action}"
        return "Action delayed — risk score too high or simulation unsafe. Continue monitoring."

    if state == "CRITICAL":
        if sim_status == "safe":
            return f"CRITICAL action executed: {action}"
        return "CRITICAL action blocked — simulation unsafe. Escalating to human operator."

    return f"Unknown state '{state}' — no action taken."