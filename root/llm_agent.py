"""
llm_agent.py
------------
LLM-powered diagnosis engine for SWIFT FHS.

Uses the custom 'swift-fhs' Ollama model (built on llama3.2, fine-tuned with
Nigerian fibre network expertise and NCC QoS knowledge via Modelfile).

Behaviour:
  - If Ollama is running and 'swift-fhs' is available → real LLM inference
  - If Ollama is unavailable / model not found → graceful fallback to the
    rule-based engine (no crash, no silent failure — logs a warning)

To activate the LLM:
  1. ollama serve                                    (start the server)
  2. cd models/.ollama
  3. ollama create swift-fhs -f Modelfile            (register the model)
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

OLLAMA_MODEL = os.environ.get("SWIFT_LLM_MODEL", "swift-fhs")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

# Set to False at module load if Ollama is confirmed unavailable
_ollama_available: bool | None = None   # None = not yet checked


# ── Ollama availability probe ──────────────────────────────────────────────────

def _check_ollama() -> bool:
    """
    Probe Ollama once to confirm it's running and 'swift-fhs' is available.
    Result is cached for the lifetime of the process.
    """
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available

    try:
        import requests
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            # Accept "swift-fhs" or "swift-fhs:latest"
            available = any(OLLAMA_MODEL in m for m in models)
            if available:
                logger.info(f"Ollama '{OLLAMA_MODEL}' model ready at {OLLAMA_BASE_URL}")
                _ollama_available = True
            else:
                logger.warning(
                    f"Ollama is running but '{OLLAMA_MODEL}' model not found. "
                    f"Available: {models}. "
                    f"Run: ollama create {OLLAMA_MODEL} -f models/.ollama/Modelfile"
                )
                _ollama_available = False
        else:
            _ollama_available = False
    except Exception as e:
        logger.warning(f"Ollama not reachable at {OLLAMA_BASE_URL} ({e}). Using rule-based fallback.")
        _ollama_available = False

    return _ollama_available


# ── LLM inference ─────────────────────────────────────────────────────────────

def _build_prompt(data: dict) -> str:
    """Build the telemetry analysis prompt sent to the LLM."""
    osnr = data.get("osnr_db", 20.0)
    ber = data.get("ber", 1e-6)
    power = data.get("power_dbm", -1.5)
    latency = data.get("latency_ms", 12.0)
    state = data.get("state", "NORMAL")
    fault_cause = data.get("fault_cause", "NONE")
    city = data.get("city", "Lagos")
    season = data.get("season", "normal")
    anomaly = data.get("anomaly_flag", 0)
    hour = data.get("hour_of_day", 12)
    risk_score = data.get("risk_score", 0.0)
    action = data.get("recommended_action", "NONE")

    # City-specific NCC OSNR minimums (from NCC_CITY_PROFILES)
    ncc_osnr = {"Lagos": 15, "Abuja": 15, "PortHarcourt": 14, "Kano": 14}
    ncc_ber = {"Lagos": 1e-5, "Abuja": 1e-5, "PortHarcourt": 1.5e-5, "Kano": 1.5e-5}
    min_osnr = ncc_osnr.get(city, 15)
    max_ber = ncc_ber.get(city, 1e-5)

    return (
        f"Analyse this Nigerian fibre telemetry and return a JSON diagnosis.\n\n"
        f"Telemetry:\n"
        f"  OSNR={osnr:.2f} dB | BER={ber:.2e} | Power={power:.1f} dBm\n"
        f"  Latency={latency:.1f} ms | RiskScore={risk_score:.2f}\n"
        f"  State={state} | FaultCause={fault_cause} | AnomalyFlag={anomaly}\n"
        f"  RecommendedAction={action}\n"
        f"  City={city} | Season={season} | HourOfDay={hour}\n\n"
        f"NCC thresholds for {city}: OSNR >= {min_osnr} dB, BER <= {max_ber:.0e}\n\n"
        f"Return valid JSON only with keys: diagnosis, root_cause, suggestion, confidence (High|Medium|Low), ncc_compliant (bool), urgency (Immediate|Scheduled|Monitor)"
    )


def _call_ollama(prompt: str) -> dict | None:
    """
    Call the Ollama API with the given prompt.
    Returns parsed dict on success, None on failure.
    """
    try:
        import requests
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.25,
                "num_ctx": 4096,
            },
        }
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Check for Ollama error in response (e.g. "Cannot read 'image.png'")
        if "error" in data:
            logger.warning(f"Ollama returned an error: {data['error'][:300]}")
            return None
        raw = data.get("response", "").strip()

        # The model is prompted to return JSON — parse it
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        return parsed

    except json.JSONDecodeError as e:
        logger.warning(f"LLM response was not valid JSON: {e}. Falling back.")
        return None
    except Exception as e:
        logger.warning(f"Ollama call failed: {e}. Falling back.")
        return None


# ── Rule-based fallback ────────────────────────────────────────────────────────

def _rule_based_diagnosis(data: dict) -> dict:
    """
    Deterministic rule-based diagnosis — always works, no external dependencies.
    Used as fallback when Ollama is unavailable.
    """
    osnr = data.get("osnr_db", 20.0)
    ber = data.get("ber", 1e-6)
    state = data.get("state", "NORMAL")
    anomaly = data.get("anomaly_flag", 0)
    fault_cause = data.get("fault_cause", "NONE")

    # Determine urgency from fault cause
    urgency_map = {
        "PHYSICAL_CUT": "Immediate",
        "GENERATOR_FAILURE": "Immediate",
        "HARMATTAN_DUST": "Scheduled",
        "RAIN_ATTENUATION": "Scheduled",
        "FIBRE_AGING": "Scheduled",
        "NONE": "Monitor",
    }
    urgency = urgency_map.get(fault_cause, "Monitor")

    ncc_compliant = osnr >= 15.0 and ber <= 1e-5

    if state == "CRITICAL" or osnr < 15:
        diagnosis = "CRITICAL: Severe signal degradation or fibre cut detected. Immediate action required."
        suggestion = "Activate protection path / reroute traffic now."
        confidence = "High"
        urgency = "Immediate"

    elif state == "DEGRADING" or osnr < 19 or anomaly == 1:
        diagnosis = "DEGRADING: Gradual fibre degradation or amplifier issue in progress."
        suggestion = "Schedule maintenance and monitor closely."
        confidence = "Medium"
        if urgency == "Monitor":
            urgency = "Scheduled"

    else:
        diagnosis = "NORMAL: Network operating within safe parameters."
        suggestion = "Continue normal monitoring."
        confidence = "High"

    return {
        "diagnosis": diagnosis,
        "root_cause": fault_cause.replace("_", " ").title() if fault_cause != "NONE" else "No fault detected",
        "suggestion": suggestion,
        "confidence": confidence,
        "ncc_compliant": ncc_compliant,
        "urgency": urgency,
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def get_llm_diagnosis(data: dict) -> dict:
    """
    Produce a structured fault diagnosis for a telemetry data row.

    Attempts real LLM inference via the 'swift-fhs' Ollama model first.
    Falls back to the deterministic rule engine if Ollama is unavailable
    or the model is not yet registered.

    Args:
        data: Single telemetry row as a dict. Expected keys:
              osnr_db, ber, power_dbm, latency_ms, state, fault_cause,
              anomaly_flag, city, season, hour_of_day.

    Returns:
        Dict with keys:
          diagnosis (str), root_cause (str), suggestion (str),
          confidence (str), ncc_compliant (bool), urgency (str),
          explanation (str), source (str: 'llm' | 'rule_engine').
    """
    result = None
    source = "rule_engine"

    # Try Ollama LLM first
    if _check_ollama():
        prompt = _build_prompt(data)
        llm_result = _call_ollama(prompt)
        if llm_result:
            result = llm_result
            source = "llm"

    # Fallback
    if result is None:
        result = _rule_based_diagnosis(data)

    # Build explanation block (unified format for both paths)
    osnr = data.get("osnr_db", 20.0)
    ber = data.get("ber", 1e-6)
    state = data.get("state", "NORMAL")
    anomaly = data.get("anomaly_flag", 0)

    explanation = (
        f"Network Analysis Report ({source.upper().replace('_', ' ')}):\n"
        f"{'-' * 40}\n"
        f"OSNR        : {osnr:.2f} dB\n"
        f"BER         : {ber:.2e}\n"
        f"State       : {state}\n"
        f"Anomaly     : {'Yes' if anomaly == 1 else 'No'}\n"
        f"City        : {data.get('city', 'N/A')} | Season: {data.get('season', 'N/A')}\n"
        f"\n"
        f"Diagnosis   : {result.get('diagnosis', '')}\n"
        f"Root Cause  : {result.get('root_cause', '')}\n"
        f"Recommend   : {result.get('suggestion', '')}\n"
        f"Confidence  : {result.get('confidence', '')}\n"
        f"Urgency     : {result.get('urgency', '')}\n"
        f"NCC OK      : {'Yes' if result.get('ncc_compliant') else 'No'}"
    )

    return {
        **result,
        "explanation": explanation,
        "source": source,
    }


def get_llm_status() -> dict:
    """Check if Ollama and the swift-fhs model are available.
    Always does a fresh probe (does not use cached result).

    Returns:
        Dict with keys: available (bool), model (str), url (str), detail (str)
    """
    reset_availability_cache()
    ok = _check_ollama()
    return {
        "available": ok,
        "model": OLLAMA_MODEL,
        "url": OLLAMA_BASE_URL,
        "detail": "Ollama connected and model found" if ok else "Ollama unreachable or model not found",
    }


def reset_availability_cache():
    """Force re-check of Ollama availability on next call (useful in tests)."""
    global _ollama_available
    _ollama_available = None


# ── 4-Line Summary Generator ─────────────────────────────────────────────────────

SUMMARY_MODEL = "nexus-chat"
SUMMARY_TIMEOUT = 180  # model cold-load may take 2+ minutes

def _build_summary_prompt(data: dict) -> str:
    """Build a prompt that asks the LLM for a 4-line structured summary."""
    summary = data.get("summary", {})
    diagnosis = data.get("diagnosis", {})
    ncc = data.get("ncc", {})
    city = summary.get("city", diagnosis.get("city", "Lagos"))
    season = summary.get("season", diagnosis.get("season", "normal"))
    state_dist = summary.get("state_distribution", {})
    total = summary.get("total_records", 0)
    normal = state_dist.get("NORMAL", 0)
    degrading = state_dist.get("DEGRADING", 0)
    critical = state_dist.get("CRITICAL", 0)
    osnr_pct = ncc.get("osnr_compliance_pct", 0)
    ber_pct = ncc.get("ber_compliance_pct", 0)
    lat_pct = ncc.get("latency_compliance_pct", 0)
    ncc_status = ncc.get("overall_status", "UNKNOWN")
    dx = diagnosis.get("diagnosis", "No diagnosis yet")
    rc = diagnosis.get("root_cause", "")
    sug = diagnosis.get("suggestion", "")
    urgency = diagnosis.get("urgency", "Monitor")

    return (
        f"As a Nigerian fibre network expert for OASIS-X, write exactly 4 lines "
        f"summarising the current situation. Use this EXACT format with these "
        f"EXACT headings:\n\n"
        f"Line 1 — PROBLEM: <one-line description of the main issue>\n"
        f"Line 2 — SITUATION CURRENTLY (WITH METRICS): <current state with key numbers>\n"
        f"Line 3 — SOLUTION (IN SIMPLE WORDS): <what to do in plain language>\n"
        f"Line 4 — <optional: a brief monitoring note if needed>\n\n"
        f"Do NOT add extra lines, headings, or commentary.\n\n"
        f"Context:\n"
        f"  City: {city} | Season: {season}\n"
        f"  Records: {total} total — {normal} normal, {degrading} degrading, {critical} critical\n"
        f"  NCC compliance: {ncc_status} (OSNR {osnr_pct}%, BER {ber_pct}%, Latency {lat_pct}%)\n"
        f"  Latest diagnosis: {dx}\n"
        f"  Root cause: {rc}\n"
        f"  Suggested action: {sug}\n"
        f"  Urgency: {urgency}"
    )


def generate_4line_summary(data: dict) -> dict:
    """Generate a 4-line structured summary of the current network situation.

    Args:
        data: dict with optional keys: summary, diagnosis, ncc (each a dict)

    Returns:
        dict with keys: lines (list[str]), raw (str), source (str)
    """
    lines = []
    raw = ""
    source = "rule"

    reset_availability_cache()
    if not _check_ollama():
        lines = _fallback_4line_summary(data)
        source = "rule"
    else:
        prompt = _build_summary_prompt(data)
        try:
            import requests
            payload = {
                "model": SUMMARY_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.25, "num_ctx": 2048},
            }
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=SUMMARY_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    logger.warning(f"Ollama returned an error in summary: {data['error'][:300]}")
                    raise Exception(data["error"])
                raw = data.get("response", "").strip()
                # Try to parse as JSON first
                try:
                    obj = json.loads(raw)
                    if isinstance(obj, dict):
                        keys = ["PROBLEM", "SITUATION CURRENTLY (WITH METRICS)", "SITUATION CURRENTLY", "SITUATION", "SOLUTION (IN SIMPLE WORDS)", "SOLUTION", "NOTE", "MONITORING NOTE", "MONITOR"]
                        for k in keys:
                            if k in obj:
                                v = obj[k]
                                if isinstance(v, dict):
                                    v = " | ".join(f"{sk}: {sv}" for sk, sv in v.items())
                                lines.append(f"{k}: {v}")
                        if lines:
                            source = "llm"
                except (json.JSONDecodeError, TypeError):
                    pass
                # If JSON parsing didn't work, try plain text format
                if not lines:
                    for line in raw.split("\n"):
                        line = line.strip()
                        if line and any(
                            line.upper().startswith(h)
                            for h in ["PROBLEM", "SITUATION", "SOLUTION", "NOTE", "MONITOR"]
                        ):
                            lines.append(line)
                    if lines:
                        source = "llm"
        except Exception as e:
            logger.warning(f"4-line summary LLM call failed: {e}. Using fallback.")

    if not lines:
        lines = _fallback_4line_summary(data)
        source = "rule"

    return {"lines": lines, "raw": raw, "source": source}


def _fallback_4line_summary(data: dict) -> list:
    """Rule-based fallback that produces the 4-line format without an LLM."""
    summary = data.get("summary", {})
    diagnosis = data.get("diagnosis", {})
    ncc = data.get("ncc", {})
    city = summary.get("city", diagnosis.get("city", "Lagos"))
    state_dist = summary.get("state_distribution", {})
    total = summary.get("total_records", 0)
    normal = state_dist.get("NORMAL", 0)
    degrading = state_dist.get("DEGRADING", 0)
    critical = state_dist.get("CRITICAL", 0)
    ncc_ok = ncc.get("overall_status", "") == "COMPLIANT"
    osnr_pct = ncc.get("osnr_compliance_pct", 0)
    dx = diagnosis.get("diagnosis", "")
    rc = diagnosis.get("root_cause", "")
    sug = diagnosis.get("suggestion", "")

    if critical > 0:
        problem = f"PROBLEM: {critical} critical links detected in {city} — immediate attention needed."
    elif degrading > 0:
        problem = f"PROBLEM: {degrading} degrading links in {city} — risk of escalation."
    else:
        problem = f"PROBLEM: Network in {city} is operating normally with no active faults."

    situation = (
        f"SITUATION CURRENTLY (WITH METRICS): {total} records — "
        f"{normal} normal, {degrading} degrading, {critical} critical. "
        f"OSNR compliance at {osnr_pct}%. NCC overall: {'COMPLIANT' if ncc_ok else 'NON-COMPLIANT'}."
    )

    if sug:
        solution = f"SOLUTION (IN SIMPLE WORDS): {sug}"
    elif critical > 0:
        solution = "SOLUTION (IN SIMPLE WORDS): Reroute traffic away from critical links immediately and dispatch a repair crew to the affected fibre span."
    elif degrading > 0:
        solution = "SOLUTION (IN SIMPLE WORDS): Schedule maintenance during off-peak hours to clean connectors and adjust amplifier gain before thresholds are breached."
    else:
        solution = "SOLUTION (IN SIMPLE WORDS): No action required — continue standard monitoring and run the next diagnostic cycle."

    note = ""
    if critical > 0 or degrading > 0:
        if "adjust" in sug.lower() or "amplifier" in sug.lower():
            note = "NOTE: Amplifier gain adjustment of +1 to +3 dB on affected spans should restore OSNR to normal range within one maintenance window."
        elif "reroute" in sug.lower():
            note = "NOTE: Protection path switching should complete in under 50 ms — verify link integrity before returning to primary fibre."

    return [problem, situation, solution] + ([note] if note else [])