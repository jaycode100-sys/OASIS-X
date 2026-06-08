from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from typing import Literal, Optional
import hashlib, json, time

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
from root.llm_agent import get_llm_diagnosis, get_llm_status, generate_4line_summary
from root.chat_agent import chat_with_llm, diagnose_ollama
from data.database import (
    save_pipeline_run, get_pipeline_runs, get_pipeline_run, delete_pipeline_run,
    save_diagnosis, save_chat_message, get_chat_history, clear_chat_history,
    log_activity, get_activities,
    get_user_profile, update_user_profile,
    create_complaint, get_complaints, get_complaint_messages,
    add_complaint_message, get_all_open_complaints, update_complaint_status,
)

router = APIRouter()

CityType = Literal["Lagos", "Abuja", "PortHarcourt", "Kano"]
SeasonType = Literal["harmattan", "rainy", "dry", "normal"]

def _run_pipeline(city, season, n, apply_drift=True):
    """Run the full pipeline — generates fresh data each call with a time-based seed."""
    t = int(time.time() * 1000) % 1000000
    df = generate_network_data(n=n, season=season, city=city, seed=t)
    if apply_drift:
        df = simulate_ncc_drift(df, city=city, drift_seed=t + 1)
    df = detect_anomalies(df, retrain=False)
    df = process_decisions(df)
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

    log_activity(
        act_type="pipeline",
        message=f"Pipeline run in {city}: {len(df)} records, {compliance.get('overall_status','?')}",
        html=f"Pipeline run: <strong>{len(df)}</strong> records in <strong>{city}</strong> | Compliance: <strong>{compliance.get('overall_status','?')}</strong>",
        user_id=_user["id"],
        username=_user["username"],
    )

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

    log_activity(
        act_type="fault",
        message=f"Fault '{event_type}' injected in {city}",
        html=f"Fault <strong>{event_type.replace('_',' ')}</strong> injected in <strong>{city}</strong> — {diagnosis.get('diagnosis','')}",
        user_id=_user["id"],
        username=_user["username"],
    )

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

    log_activity(
        act_type="diagnose",
        message=f"Diagnosed row {row_index} in {city}",
        html=f"Diagnosed row <strong>#{row_index}</strong> in <strong>{city}</strong> — {diagnosis.get('diagnosis','')}",
        user_id=_user["id"],
        username=_user["username"],
    )

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


# ── 4-Line Summary ───────────────────────────────────────────────────────────────

@router.post("/summarize")
def summarize_network(
    _user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """Generate a 4-line structured summary of the current network situation
    using an LLM.  Provide 'summary', 'diagnosis', and/or 'ncc' keys in the body.

    Returns:
        lines (list[str]), raw (str), source (str)
    """
    result = generate_4line_summary(body)
    return result


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


@router.get("/chat/diagnose")
def chat_diagnose(_user: dict = Depends(get_current_user)):
    """Run comprehensive Ollama diagnostics and return raw results."""
    return diagnose_ollama()


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


# ── User Profile ─────────────────────────────────────────────────────────────────────

@router.get("/profile")
def get_profile(_user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    profile = get_user_profile(_user["id"])
    if not profile:
        return {"profile": None}
    return {"profile": profile}


@router.put("/profile")
def update_profile(
    _user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """Update the current user's profile (theme, display_name, avatar_color, settings)."""
    profile = update_user_profile(_user["id"], **body)
    return {"profile": profile}


# ── Complaints (per-user) ────────────────────────────────────────────────────────────

@router.post("/complaints")
def create_complaint_endpoint(
    _user: dict = Depends(get_current_user),
    subject: str = Body(..., embed=True),
):
    """Create a new complaint (for regular users to chat with agent)."""
    c = create_complaint(_user["id"], subject)
    return {"complaint": c}


@router.get("/complaints")
def list_complaints(
    _user: dict = Depends(get_current_user),
    status: str = Query(None),
):
    """List complaints. Regular users see their own; superadmin sees all."""
    if _user["role"] == "superadmin":
        complaints = get_complaints(user_id=None, status=status) if status else get_all_open_complaints()
    else:
        complaints = get_complaints(user_id=_user["id"], status=status)
    return {"complaints": complaints}


@router.get("/complaints/{complaint_id}/messages")
def get_complaint_messages_endpoint(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
):
    """Get messages for a complaint."""
    msgs = get_complaint_messages(complaint_id)
    return {"messages": msgs}


@router.post("/complaints/{complaint_id}/messages")
def post_complaint_message(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
    message: str = Body(..., embed=True),
):
    """Add a message to a complaint. Superadmin auto-assigned."""
    msg = add_complaint_message(complaint_id, _user["id"], message)
    if _user["role"] == "superadmin":
        update_complaint_status(complaint_id, "open", assigned_to=_user["id"])
    return {"message": msg}


@router.post("/complaints/{complaint_id}/close")
def close_complaint(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
):
    """Close a complaint."""
    c = update_complaint_status(complaint_id, "closed")
    return {"complaint": c}


# ── Activity Log ──────────────────────────────────────────────────────────────────

@router.post("/activity")
def create_activity(
    request: Request,
    _user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """Log an activity entry."""
    log_activity(
        act_type=body.get("type", "system"),
        message=body.get("message", ""),
        html=body.get("html"),
        user_id=_user["id"],
        username=_user["username"],
    )
    return {"logged": True}


@router.get("/activity")
def list_activities(
    _user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    own: bool = Query(False),
):
    """List recent activity log entries. Superadmin can see all; regular users
    can see their own activities by passing `own=true`."""
    if own:
        return {"activities": get_activities(limit, user_id=_user["id"])}
    if _user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can view all activity logs")
    return {"activities": get_activities(limit)}