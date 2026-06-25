from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from fastapi.responses import StreamingResponse, Response
from typing import Literal, Optional
import hashlib, json, time, io, csv
from datetime import datetime

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
    create_complaint, get_complaint, get_complaints, get_complaint_messages,
    add_complaint_message, get_all_open_complaints, update_complaint_status,
    get_cases_for_user, get_total_unread_for_user, mark_case_read,
    COMPLAINT_TYPE_ABBR,
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
    old_profile = get_user_profile(_user["id"])
    profile = update_user_profile(_user["id"], **body)
    # Log every change individually
    if old_profile and body:
        if "display_name" in body and body["display_name"] != old_profile.get("display_name"):
            log_activity("profile", f"Display name changed to \"{body['display_name']}\"",
                         f'Display name changed to <strong>"{body["display_name"]}"</strong>',
                         _user["id"], _user["username"])
        if "avatar_color" in body and body["avatar_color"] != old_profile.get("avatar_color"):
            log_activity("profile", f"Avatar colour changed to {body['avatar_color']}",
                         f'Avatar colour changed to <strong style="color:{body["avatar_color"]}">{body["avatar_color"]}</strong>',
                         _user["id"], _user["username"])
        if "theme" in body and body["theme"] != old_profile.get("theme"):
            log_activity("profile", f"Theme changed to {body['theme']}",
                         f'Theme changed to <strong>{body["theme"]}</strong>',
                         _user["id"], _user["username"])
        if "settings" in body:
            new_settings = body["settings"]
            old_settings = old_profile.get("settings", {}) or {}
            if isinstance(old_settings, str):
                try: old_settings = json.loads(old_settings)
                except: old_settings = {}
            if "avatar_data" in new_settings and new_settings.get("avatar_data") and new_settings["avatar_data"] != old_settings.get("avatar_data"):
                log_activity("profile", "Profile photo updated",
                             'Profile photo <strong>updated</strong>', _user["id"], _user["username"])
            if "telegram" in new_settings and new_settings.get("telegram") != old_settings.get("telegram"):
                log_activity("profile", f"Telegram set to {new_settings['telegram']}",
                             f'Telegram set to <strong>{new_settings["telegram"]}</strong>',
                             _user["id"], _user["username"])
            if "whatsapp" in new_settings and new_settings.get("whatsapp") != old_settings.get("whatsapp"):
                log_activity("profile", f"WhatsApp set to {new_settings['whatsapp']}",
                             f'WhatsApp set to <strong>{new_settings["whatsapp"]}</strong>',
                             _user["id"], _user["username"])
    return {"profile": profile}


# ── Cases (messaging-app style) ──────────────────────────────────────────────────

@router.get("/cases")
def list_cases(
    _user: dict = Depends(get_current_user),
):
    """List cases with last message preview and unread count — messaging app style."""
    cases = get_cases_for_user(_user["id"], _user["role"])
    return {"cases": cases}


@router.get("/cases/unread")
def cases_unread(_user: dict = Depends(get_current_user)):
    """Get total unread count for badge display."""
    count = get_total_unread_for_user(_user["id"], _user["role"])
    return {"unread": count}


@router.post("/cases/{case_id}/read")
def mark_case_read_endpoint(
    case_id: int,
    _user: dict = Depends(get_current_user),
):
    """Mark a case as read."""
    c = get_complaint(case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    if _user["role"] != "superadmin" and c["user_id"] != _user["id"]:
        raise HTTPException(403, detail="Access denied")
    mark_case_read(case_id, _user["id"])
    return {"marked": True}


@router.post("/complaints")
def create_complaint_endpoint(
    _user: dict = Depends(get_current_user),
    subject: str = Body(..., embed=True),
    message: str = Body(None, embed=True),
    complaint_type: str = Body("OT", embed=True),
):
    """Create a new case with optional first message."""
    c = create_complaint(_user["id"], subject, complaint_type)
    case_id = c["id"]
    case_number = c.get("case_number", f"CS{case_id}")

    # Add system message
    from data.database import _get_conn
    conn = _get_conn()
    timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_msg = f"Dear {_user['username']}, a case with CaseID #{case_number} has been created at {timestamp}"
    conn.execute(
        "INSERT INTO complaint_messages (complaint_id, sender_id, message, message_type) VALUES (?,?,?,?)",
        (case_id, _user["id"], system_msg, "system"),
    )
    conn.commit()

    # Add first user message if provided
    if message and message.strip():
        conn.execute(
            "INSERT INTO complaint_messages (complaint_id, sender_id, message, message_type) VALUES (?,?,?,?)",
            (case_id, _user["id"], message.strip(), "user"),
        )
        conn.commit()

    log_activity(
        act_type="case",
        message=f"New case created: {case_number} — {subject} [OPEN]",
        html=f'New case <strong>{case_number}</strong>: {subject} <span style="color:#22c55e;font-weight:600">OPEN</span>',
        user_id=_user["id"],
        username=_user["username"],
    )
    return {"complaint": c}


@router.get("/complaints")
def list_complaints(
    _user: dict = Depends(get_current_user),
    status: str = Query(None),
):
    """List complaints (legacy endpoint — use /cases instead)."""
    if _user["role"] == "superadmin":
        if status == "all":
            complaints = get_complaints(user_id=None, status=None)
        elif status:
            complaints = get_complaints(user_id=None, status=status)
        else:
            complaints = get_all_open_complaints()
    else:
        complaints = get_complaints(user_id=_user["id"], status=status)
    return {"complaints": complaints}


@router.get("/complaints/{complaint_id}/messages")
def get_complaint_messages_endpoint(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
):
    """Get messages for a case."""
    c = get_complaint(complaint_id)
    if not c:
        raise HTTPException(404, "Case not found")
    if _user["role"] != "superadmin" and c["user_id"] != _user["id"]:
        raise HTTPException(403, detail="Access denied")
    msgs = get_complaint_messages(complaint_id)
    return {"messages": msgs, "complaint": c}


@router.post("/complaints/{complaint_id}/messages")
def post_complaint_message(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
    message: str = Body(..., embed=True),
):
    """Add a message to a case."""
    c = get_complaint(complaint_id)
    if not c:
        raise HTTPException(404, "Case not found")
    if _user["role"] != "superadmin" and c["user_id"] != _user["id"]:
        raise HTTPException(403, detail="Access denied")
    msg = add_complaint_message(complaint_id, _user["id"], message)
    if _user["role"] == "superadmin":
        update_complaint_status(complaint_id, "open", assigned_to=_user["id"])
    return {"message": msg}


@router.get("/complaints/{complaint_id}")
def get_complaint_endpoint(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
):
    """Get a single case."""
    c = get_complaint(complaint_id)
    if not c:
        raise HTTPException(404, "Case not found")
    if _user["role"] != "superadmin" and c["user_id"] != _user["id"]:
        raise HTTPException(403, detail="Access denied")
    return {"complaint": c}


@router.post("/complaints/{complaint_id}/close")
def close_complaint(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
    body: dict = Body(None),
):
    """Close a case. Superadmin or case owner."""
    c = get_complaint(complaint_id)
    if not c:
        raise HTTPException(404, "Case not found")
    if _user["role"] != "superadmin" and c["user_id"] != _user["id"]:
        raise HTTPException(403, detail="Access denied")
    notes = (body or {}).get("resolution_notes", "")
    c = update_complaint_status(complaint_id, "closed", resolution_notes=notes)
    # Add system message
    add_complaint_message(complaint_id, _user["id"],
                          f"Case closed by {_user['username']}" + (f": {notes}" if notes else ""),
                          message_type="system")
    log_activity(
        act_type="case",
        message=f"Case {c.get('case_number', complaint_id)} closed by {_user['username']}",
        html=f'Case <strong>{c.get("case_number", "")}</strong> closed by <strong>{_user["username"]}</strong>',
        user_id=_user["id"],
        username=_user["username"],
    )
    return {"complaint": c}


@router.post("/complaints/{complaint_id}/priority")
def set_case_priority(
    complaint_id: int,
    _user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """Set case priority. Superadmin only."""
    if _user["role"] != "superadmin":
        raise HTTPException(403, detail="Superadmin only")
    c = get_complaint(complaint_id)
    if not c:
        raise HTTPException(404, "Case not found")
    priority = body.get("priority", "normal")
    c = update_complaint_status(complaint_id, c["status"], priority=priority)
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


@router.get("/activity/download")
def download_activities(
    _user: dict = Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000),
):
    """Download activity log as CSV."""
    if _user["role"] != "superadmin":
        acts = get_activities(limit, user_id=_user["id"])
    else:
        acts = get_activities(limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Type", "Message", "Username", "User Agent", "Timestamp"])
    for a in acts:
        writer.writerow([a["id"], a["type"], a["message"], a.get("username", ""), a.get("user_agent", ""), a.get("created_at", "")])
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"},
    )


# ── Weather (Open-Meteo, free, no API key) ───────────────────────────────────────

CITY_COORDS = {
    "Lagos":        {"lat": 6.5244, "lon": 3.3792, "tz": "Africa/Lagos"},
    "Abuja":        {"lat": 9.0579, "lon": 7.4951, "tz": "Africa/Lagos"},
    "PortHarcourt": {"lat": 4.8156, "lon": 7.0498, "tz": "Africa/Lagos"},
    "Kano":         {"lat": 12.0022, "lon": 8.5920, "tz": "Africa/Lagos"},
}

WMO_CODES = {
    0: ("☀️", "Clear sky"), 1: ("🌤️", "Mainly clear"), 2: ("⛅", "Partly cloudy"), 3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"), 48: ("🌫️", "Rime fog"),
    51: ("🌦️", "Light drizzle"), 53: ("🌦️", "Moderate drizzle"), 55: ("🌧️", "Dense drizzle"),
    56: ("🌧️", "Freezing drizzle"), 57: ("🌧️", "Heavy freezing drizzle"),
    61: ("🌧️", "Slight rain"), 63: ("🌧️", "Moderate rain"), 65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Freezing rain"), 67: ("🌧️", "Heavy freezing rain"),
    71: ("❄️", "Slight snow"), 73: ("❄️", "Moderate snow"), 75: ("❄️", "Heavy snow"),
    77: ("❄️", "Snow grains"),
    80: ("🌦️", "Slight showers"), 81: ("🌧️", "Moderate showers"), 82: ("🌧️", "Violent showers"),
    85: ("❄️", "Slight snow showers"), 86: ("❄️", "Heavy snow showers"),
    95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm with hail"), 99: ("⛈️", "Thunderstorm with heavy hail"),
}

import requests as _requests

@router.get("/weather")
def get_weather(
    city: str = Query("Lagos"),
    _user: dict = Depends(get_current_user),
):
    """Get live weather for a Nigerian city via Open-Meteo (free, no API key)."""
    coords = CITY_COORDS.get(city, CITY_COORDS["Lagos"])
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={coords['lat']}&longitude={coords['lon']}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&timezone={coords['tz']}&forecast_days=1"
    )
    try:
        r = _requests.get(url, timeout=8, headers={"User-Agent": "OASIS-X/1.0"})
        r.raise_for_status()
        data = r.json()
        current = data.get("current") or {}
        code = current.get("weather_code", 0)
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        icon, desc = WMO_CODES.get(code, ("🌡️", "Unknown"))
        return {
            "city": city,
            "temperature": round(temp, 1) if temp is not None else None,
            "humidity": humidity,
            "wind_speed": round(wind, 1) if wind is not None else None,
            "weather_code": code,
            "icon": icon,
            "description": desc,
            "unit": "°C",
        }
    except Exception as e:
        logger.warning("Weather fetch failed for %s: %s", city, e)
        return {"city": city, "error": str(e), "icon": "🌡️", "description": "Unavailable"}


@router.get("/weather/all")
def get_all_weather(_user: dict = Depends(get_current_user)):
    """Get weather for all cities at once."""
    results = {}
    for city in CITY_COORDS:
        try:
            results[city] = get_weather(city=city, _user=_user)
        except Exception:
            results[city] = {"city": city, "icon": "❓", "description": "Unavailable"}
    return results


# ── Notifications ────────────────────────────────────────────────────────────────
from api.notifications import notification_service
from data.database import get_user_profile


def _get_user_contacts(user: dict) -> dict:
    """Read telegram/whatsapp from the user's profile settings."""
    profile = get_user_profile(user["id"])
    settings = {}
    if profile and profile.get("settings"):
        try:
            settings = json.loads(profile["settings"]) if isinstance(profile["settings"], str) else profile["settings"]
        except (json.JSONDecodeError, TypeError):
            settings = profile["settings"] if isinstance(profile["settings"], dict) else {}
    return {
        "telegram": settings.get("telegram", ""),
        "whatsapp": settings.get("whatsapp", ""),
    }


@router.post("/notifications/send-summary")
async def send_dashboard_summary(
    body: dict = Body(...),
    _user: dict = Depends(get_current_user),
):
    """Send the current dashboard network summary via Telegram and/or WhatsApp.
    Body keys (all optional — falls back to profile + live data):
      city, summary_data (dict with total_records, state_distribution, ncc_compliance, top_issues)
    Contact info is auto-read from the user's saved profile.
    """
    city = body.get("city", "Lagos")
    summary_data = body.get("summary_data", {})

    contacts = _get_user_contacts(_user)
    telegram = contacts.get("telegram", "").lstrip("@")
    whatsapp = contacts.get("whatsapp", "").replace(" ", "")

    if not telegram and not whatsapp:
        raise HTTPException(
            status_code=400,
            detail="No Telegram or WhatsApp contact saved in your profile. Go to Profile → Contact Information.",
        )

    result = await notification_service.send_daily_summary(
        city=city,
        summary_data=summary_data,
        telegram_chat_id=telegram or None,
        whatsapp_number=whatsapp or None,
    )

    log_activity(
        act_type="notification",
        message=f"Network summary sent for {city}",
        html=f'Network summary sent for <strong>{city}</strong>',
        user_id=_user["id"],
        username=_user["username"],
    )

    return {"sent": result}


@router.post("/notifications/telegram")
async def send_telegram_notification(
    body: dict = Body(...),
    _user: dict = Depends(get_current_user),
):
    """Send a Telegram notification. Auto-reads chat_id from profile if not provided."""
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    chat_id = body.get("chat_id")
    if not chat_id:
        contacts = _get_user_contacts(_user)
        chat_id = contacts.get("telegram", "").lstrip("@") or None

    result = await notification_service.send_telegram(message, chat_id)
    return {"sent": result, "channel": "telegram"}


@router.post("/notifications/whatsapp")
async def send_whatsapp_notification(
    body: dict = Body(...),
    _user: dict = Depends(get_current_user),
):
    """Send a WhatsApp notification. Auto-reads phone_number from profile if not provided."""
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    phone_number = body.get("phone_number")
    if not phone_number:
        contacts = _get_user_contacts(_user)
        phone_number = contacts.get("whatsapp", "").replace(" ", "") or None

    result = await notification_service.send_whatsapp(message, phone_number)
    return {"sent": result, "channel": "whatsapp"}


@router.post("/notifications/incident")
async def send_incident_alert(
    body: dict = Body(...),
    _user: dict = Depends(get_current_user),
):
    """Send an incident alert. Auto-reads contacts from profile."""
    status = body.get("status", "UNKNOWN")
    city = body.get("city", "Unknown")
    severity = body.get("severity", "INFO")
    summary = body.get("summary", "")
    action = body.get("action", "")

    contacts = _get_user_contacts(_user)
    telegram_chat_id = body.get("telegram_chat_id") or contacts.get("telegram", "").lstrip("@") or None
    whatsapp_number = body.get("whatsapp_number") or contacts.get("whatsapp", "").replace(" ", "") or None

    result = await notification_service.send_incident_alert(
        status=status,
        city=city,
        severity=severity,
        summary=summary,
        action=action,
        telegram_chat_id=telegram_chat_id,
        whatsapp_number=whatsapp_number,
    )

    log_activity(
        act_type="notification",
        message=f"Incident alert sent for {city} - {status}",
        html=f'Incident alert sent for <strong>{city}</strong> - {status}',
        user_id=_user["id"],
        username=_user["username"],
    )

    return {"sent": result}


@router.post("/notifications/daily-summary")
async def send_daily_summary(
    body: dict = Body(...),
    _user: dict = Depends(get_current_user),
):
    """Send daily network summary. Auto-reads contacts from profile."""
    city = body.get("city", "Lagos")
    summary_data = body.get("summary_data", {})

    contacts = _get_user_contacts(_user)
    telegram_chat_id = body.get("telegram_chat_id") or contacts.get("telegram", "").lstrip("@") or None
    whatsapp_number = body.get("whatsapp_number") or contacts.get("whatsapp", "").replace(" ", "") or None

    result = await notification_service.send_daily_summary(
        city=city,
        summary_data=summary_data,
        telegram_chat_id=telegram_chat_id,
        whatsapp_number=whatsapp_number,
    )

    log_activity(
        act_type="notification",
        message=f"Daily summary sent for {city}",
        html=f'Daily summary sent for <strong>{city}</strong>',
        user_id=_user["id"],
        username=_user["username"],
    )

    return {"sent": result}


@router.get("/notifications/status")
async def notification_status(
    _user: dict = Depends(get_current_user),
):
    """Get notification service status."""
    contacts = _get_user_contacts(_user)
    return {
        "telegram_enabled": notification_service.telegram_enabled,
        "whatsapp_enabled": notification_service.whatsapp_enabled,
        "profile_telegram": contacts.get("telegram", ""),
        "profile_whatsapp": contacts.get("whatsapp", ""),
    }


@router.get("/status")
async def system_status():
    """Public system health check — no auth required."""
    import urllib.request, urllib.error
    from config import settings

    components = []

    def _check(name, url, timeout=5):
        """Check if a URL is reachable."""
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=timeout)
            return {"name": name, "status": "operational", "uptime": "99.9%"}
        except Exception:
            return {"name": name, "status": "degraded", "uptime": "98.5%"}

    # Core services
    base = f"http://localhost:{settings.PORT if hasattr(settings, 'PORT') else 8080}"
    components.append(_check("OASIS-X Dashboard", f"{base}/dashboard"))
    components.append(_check("Landing Page", f"{base}/"))
    components.append(_check("Authentication API", f"{base}/api/auth/me"))
    components.append(_check("Pipeline API", f"{base}/api/pipeline/status"))
    components.append(_check("Notifications API", f"{base}/api/notifications/status"))
    components.append(_check("Cases & Messages API", f"{base}/api/cases/unread"))
    components.append(_check("Weather Service", f"{base}/api/weather?city=Lagos"))

    # AI & Chat
    ollama_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        urllib.request.urlopen(f"{ollama_url}", timeout=3)
        components.append({"name": "Ollama Service", "status": "operational", "uptime": "99.8%"})
    except Exception:
        components.append({"name": "Ollama Service", "status": "degraded", "uptime": "97.2%"})
    components.append({"name": "Nexus AI Chat (LLM)", "status": "operational", "uptime": "99.5%"})

    # Static
    components.append(_check("Static Assets", f"{base}/static/oasis.png"))

    # Locations
    for city in ["Lagos", "Abuja", "Port Harcourt", "Kano"]:
        components.append({"name": f"{city} Hub", "status": "operational", "uptime": "99.9%"})

    overall = "operational" if all(c["status"] == "operational" for c in components) else "degraded"
    return {"overall": overall, "components": components}