from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Literal, Optional
import hashlib, json

from api.auth import get_current_user
from models.data_simulator import generate_network_data
from models.anomaly_detector import detect_anomalies
from models.ncc_feed import (
    get_ncc_baseline,
    get_current_season,
    simulate_ncc_drift,
    evaluate_against_ncc,
    NCC_CITY_PROFILES,
)
from root.decision_engine import process_decisions, validate_and_execute
from root.llm_agent import get_llm_diagnosis, get_llm_status
from root.chat_agent import chat_with_llm
from data.database import (
    save_pipeline_run, get_pipeline_runs, get_pipeline_run, delete_pipeline_run,
    save_diagnosis, save_chat_message, get_chat_history, clear_chat_history,
)

router = APIRouter()

CityType = Literal["Lagos", "Abuja", "PortHarcourt", "Kano"]
SeasonType = Literal["harmattan", "rainy", "dry", "normal"]

# Simple in-memory cache keyed by (city, season, n)
_pipeline_cache: dict = {}

def _run_pipeline(city, season, n, apply_drift=True):
    """Run or return cached pipeline result."""
    key = f"{city}:{season}:{n}"
    if key in _pipeline_cache:
        return _pipeline_cache[key]
    df = generate_network_data(n=n, season=season, city=city)
    if apply_drift:
        df = simulate_ncc_drift(df, city=city)
    df = detect_anomalies(df, retrain=False)
    df = process_decisions(df)
    _pipeline_cache[key] = df
    return df


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/status")
def status():
    """Health check — confirms the API and pipeline modules are reachable."""
    return {
        "system": "running",
        "service": "SWIFT FHS",
        "version": "1.0.0",
        "supported_cities": list(NCC_CITY_PROFILES.keys()),
        "current_season": get_current_season(),
    }


@router.get("/llm-status")
def llm_status():
    """Check whether the Ollama LLM (swift-fhs model) is available."""
    return get_llm_status()


# ── Pipeline ───────────────────────────────────────────────────────────────────

@router.get("/run")
def run_pipeline(
    _user: dict = Depends(get_current_user),
    city: CityType = Query("Lagos", description="Nigerian city context"),
    season: SeasonType = Query(None, description="Environmental season. Defaults to current calendar season."),
    apply_ncc_drift: bool = Query(True, description="Apply live NCC feed drift to the telemetry"),
    n: int = Query(200, ge=50, le=1000, description="Number of telemetry samples to generate"),
):
    """
    Run a full Nigerian-context pipeline pass:
    generate → NCC drift → detect anomalies → classify → recommend actions.

    Returns the last 15 processed rows (covers the fault period) plus a
    summary and NCC compliance report.
    """
    effective_season = season or get_current_season()

    df = _run_pipeline(city, effective_season, n, apply_ncc_drift)

    # NCC compliance evaluation
    compliance = evaluate_against_ncc(df)

    # Summary statistics
    summary = {
        "total_records": len(df),
        "city": city,
        "season": effective_season,
        "ncc_drift_applied": apply_ncc_drift,
        "state_distribution": df["state"].value_counts().to_dict(),
        "action_distribution": df["recommended_action"].value_counts().to_dict(),
        "event_distribution": df["event"].value_counts().to_dict(),
        "fault_causes": df["fault_cause"].value_counts().to_dict(),
        "ncc_compliance": compliance,
    }

    # Return last 15 rows (fault zone + context)
    cols = ["time", "hour_of_day", "osnr_db", "ber", "power_dbm", "latency_ms",
            "event", "fault_cause", "state", "recommended_action",
            "risk_score", "environmental_factor"]
    available_cols = [c for c in cols if c in df.columns]
    rows = df.tail(15)[available_cols].to_dict(orient="records")

    return {"summary": summary, "rows": rows}


# ── Nigerian Context ───────────────────────────────────────────────────────────

@router.get("/nigerian-context")
def nigerian_context(
    _user: dict = Depends(get_current_user),
    city: CityType = Query("Lagos", description="City to retrieve NCC baseline for"),
):
    """
    Return NCC QoS baselines, thresholds, and risk factors for the given city.
    Also includes the current inferred environmental season.
    """
    baseline = get_ncc_baseline(city)
    baseline["current_season"] = get_current_season()
    return baseline


@router.get("/nigerian-context/all-cities")
def all_city_profiles(_user: dict = Depends(get_current_user)):
    """Return NCC baseline profiles for all supported Nigerian cities."""
    return {
        city: get_ncc_baseline(city)
        for city in NCC_CITY_PROFILES
    }


# ── On-Demand Fault Injection ─────────────────────────────────────────────────

@router.get("/simulate/event/{event_type}")
def simulate_event(
    event_type: Literal[
        "generator_failure",
        "fiber_cut",
        "harmattan_degradation",
        "rain_attenuation",
        "peak_congestion",
    ],
    city: CityType = Query("Lagos"),
    row_index: int = Query(100, ge=0, le=199, description="Which telemetry row to diagnose post-fault"),
    _user: dict = Depends(get_current_user),
):
    """
    Inject a specific Nigerian fault event into the simulated network and
    return the diagnosis for the affected row.

    Supported events:
    - generator_failure       — power infrastructure outage
    - fiber_cut               — physical cable cut
    - harmattan_degradation   — dust-driven OSNR attenuation
    - rain_attenuation        — heavy rain power drop
    - peak_congestion         — Lagos evening usage peak
    """
    # Map event type to season / simulator config
    season_map = {
        "generator_failure":    "normal",
        "fiber_cut":            "normal",
        "harmattan_degradation":"harmattan",
        "rain_attenuation":     "rainy",
        "peak_congestion":      "normal",
    }
    season = season_map[event_type]
    inject_gen = event_type == "generator_failure"

    df = generate_network_data(
        n=200,
        season=season,
        city=city,
        inject_generator_failure=inject_gen,
    )
    df = simulate_ncc_drift(df, city=city)
    df = detect_anomalies(df, retrain=False)
    df = process_decisions(df)

    row_index = min(row_index, len(df) - 1)
    row = df.iloc[row_index].to_dict()
    diagnosis = get_llm_diagnosis(row)

    return {
        "event_injected": event_type,
        "city": city,
        "season": season,
        "row_index": row_index,
        "telemetry": {
            k: row.get(k)
            for k in ["time", "hour_of_day", "osnr_db", "ber",
                      "power_dbm", "latency_ms", "event",
                      "fault_cause", "state", "recommended_action"]
        },
        **diagnosis,
    }


# ── Row-Level Diagnosis ────────────────────────────────────────────────────────

@router.get("/diagnose/{row_index}")
def diagnose_row(
    row_index: int,
    city: CityType = Query("Lagos"),
    season: SeasonType = Query(None),
    _user: dict = Depends(get_current_user),
):
    """
    Run the full Nigerian pipeline and return a structured diagnosis for
    the specified telemetry row index (0–199).
    """
    effective_season = season or get_current_season()

    df = _run_pipeline(city, effective_season, 200)

    if row_index < 0 or row_index >= len(df):
        raise HTTPException(status_code=400, detail=f"row_index must be 0-{len(df) - 1}")

    row = df.iloc[row_index].to_dict()
    diagnosis = get_llm_diagnosis(row)

    return {
        "row_index": row_index,
        "city": city,
        "season": effective_season,
        "telemetry": {
            k: row.get(k)
            for k in ["time", "hour_of_day", "osnr_db", "ber", "power_dbm",
                      "latency_ms", "event", "fault_cause", "state",
                      "recommended_action", "environmental_factor"]
        },
        **diagnosis,
    }


# ── Pipeline Logs (SQLite) ─────────────────────────────────────────────────────

@router.post("/logs")
def log_pipeline_run(
    _user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """Save a pipeline run to the database."""
    run_id = save_pipeline_run(
        city=body.get("city", "Lagos"),
        season=body.get("season"),
        n_samples=body.get("n", 200),
        rows=body.get("rows", []),
        summary=body.get("summary", {}),
        ncc_compliance=body.get("ncc_compliance", {}),
    )
    return {"saved": True, "run_id": run_id}


@router.get("/logs")
def list_logs(
    _user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """List saved pipeline runs."""
    return {"runs": get_pipeline_runs(limit)}


@router.get("/logs/{run_id}")
def get_log(
    run_id: int,
    _user: dict = Depends(get_current_user),
):
    """Get a specific pipeline run with its telemetry rows."""
    run = get_pipeline_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.delete("/logs/{run_id}")
def delete_log(
    run_id: int,
    _user: dict = Depends(get_current_user),
):
    """Delete a pipeline run and its telemetry rows."""
    delete_pipeline_run(run_id)
    return {"deleted": True, "run_id": run_id}


# ── Chat Agent ──────────────────────────────────────────────────────────────────

@router.get("/chat/history")
def chat_history(_user: dict = Depends(get_current_user)):
    """Return recent chat messages."""
    return {"messages": get_chat_history()}


@router.delete("/chat/history")
def clear_chat(_user: dict = Depends(get_current_user)):
    """Clear all chat messages."""
    clear_chat_history()
    return {"cleared": True}


@router.post("/chat")
def chat(
    _user: dict = Depends(get_current_user),
    message: str = Body(..., embed=True),
    mode: str = Body("technical", embed=True),
    context: Optional[dict] = Body(None, embed=True),
):
    """Send a message to the OASIS-X chat agent and get a reply.
    
    mode: 'technical' for field engineers (precise metrics, dB values, NCC thresholds)
          'simple' for non-technical users (plain language, analogies)
    """
    save_chat_message("user", message)
    result = chat_with_llm(message, context, mode=mode)
    reply = result.get("reply", "")
    save_chat_message("assistant", reply)
    return {"reply": reply, "source": result.get("source", "unknown")}