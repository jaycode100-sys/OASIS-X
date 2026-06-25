"""
Nexus Chat Agent — robust conversational AI for OASIS-X.

Uses requests (non-streaming) for reliability, tries multiple models,
and includes a comprehensive OASIS-X knowledge lexicon. Falls back to
rule-based responses for greetings and common questions when LLM is down.
"""
import json, logging, os, re
import requests as _requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

CHAT_MODEL = "nexus-chat"
MODELS_TO_TRY = ["qwen2.5:0.5b", "nexus-chat", "llama3.2:1b", "swift-fhs"]

_TRACE_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chat_trace.log")


def _trace(msg: str):
    print(f"[CHAT_TRACE] {msg}", flush=True)
    logger.debug(msg)
    try:
        with open(_TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


# ── Greeting Detection ─────────────────────────────────────────────────────────
_GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|yo|sup|what'?s\s+up|how\s+are\s+you|good\s+(morning|afternoon|evening|day)"
    r"|howdy|greetings|hiya|how(.*?)do(.*?ing)?|what's\s+good|hola|welcome|namaste|cheers"
    r"|thanks|thank\s*you|thx|ok|okay|sure|nice|cool|great|awesome|perfect|wow|lol|heya"
    r"|how\s+is\s+it\s+going|how('?s|\s+is)\s+things|what('?s|\s+is)\s+new"
    r"|good\s+day|gday|top\s+of\s+the\s+morning|rise\s+and\s+shine)\s*[!.?]*$",
    re.IGNORECASE,
)

_GREETING_RESPONSES = [
    "Hey there! 👋 I'm Nexus, your AI network assistant. I can help you understand fibre telemetry, NCC compliance, fault diagnosis, or anything about the OASIS-X dashboard. What would you like to know?",
    "Hello! 😊 Great to have you here. I'm Nexus — ask me about OSNR readings, BER thresholds, network health, or just chat about how the dashboard works!",
    "Hi! Welcome to OASIS-X. I'm your network companion — whether it's troubleshooting fibre faults, explaining compliance metrics, or walking you through the dashboard. What's on your mind?",
    "Hey! 👋 Nexus here. I'm ready to help with anything — from casual questions about the system to deep technical analysis. What would you like to explore?",
    "Hello! 😊 I'm Nexus, your OASIS-X assistant. Feel free to ask about the telemetry data, network status, fault types, or anything else. How can I help?",
]

_THANKS_RESPONSES = [
    "You're welcome! 😊 Let me know if there's anything else you'd like to know about the network or the dashboard.",
    "Happy to help! Don't hesitate to ask if you have more questions about the system.",
    "Anytime! I'm here whenever you need help with OASIS-X. 🙌",
]


def _is_greeting(message: str) -> str | None:
    """Return a conversational response for greetings, or None if not a greeting."""
    msg = message.strip().lower()
    if _GREETING_PATTERNS.match(msg):
        import random
        if any(w in msg for w in ["thank", "thx", "thanks", "appreciate"]):
            return random.choice(_THANKS_RESPONSES)
        return random.choice(_GREETING_RESPONSES)
    return None


# ── OASIS-X Knowledge Lexicon ──────────────────────────────────────────────────
LEXICON = """
== OASIS-X COMPLETE KNOWLEDGE REFERENCE ==

PROJECT OVERVIEW:
OASIS-X (Smart Waveform Integrated Fibre-optic Transmission — Fault Healing System) is a real-time autonomous optical fibre fault healing dashboard for Nigerian networks. It monitors fibre health, detects faults using ML, and initiates healing protocols automatically.

CITIES MONITORED:
• Lagos — largest metro, high congestion, rainy season impact (Apr–Oct)
• Abuja — federal capital, moderate load, harmattan dust (Nov–Feb)
• Port Harcourt (PH) — oil region, high humidity, rain attenuation
• Kano — northern hub, extreme harmattan Nov–Feb, dust reduces OSNR

SEASONS:
• Harmattan (Nov–Feb): Dust particles reduce OSNR by ~2dB, especially in Kano/Abuja
• Rainy (Apr–Oct): Heavy rain reduces optical power by 2.5–6dB in Lagos/PH
• Dry (Jul–Sep): Normal conditions, low interference
• Normal (Oct): Transition month, baseline conditions

NCC QoS THRESHOLDS (Nigerian Communications Commission):
| City           | Min OSNR (dB) | Max BER      | Max Latency |
|----------------|---------------|--------------|-------------|
| Lagos          | 15            | 1×10⁻⁵      | 150ms       |
| Abuja          | 15            | 1×10⁻⁵      | 150ms       |
| Port Harcourt  | 14            | 1.5×10⁻⁵    | 150ms       |
| Kano           | 14            | 1.5×10⁻⁵    | 150ms       |

NETWORK STATES:
• NORMAL: OSNR ≥ 19dB, BER ≤ 1×10⁻⁶ — all metrics within safe limits
• DEGRADING: OSNR 15–19dB or BER 1×10⁻⁶ to 1×10⁻⁵ — approaching thresholds
• CRITICAL: OSNR < 15dB or BER > 1×10⁻⁵ — immediate action required

FAULT TYPES:
1. FIBRE_CUT (PHYSICAL_CUT): Cable physically broken. OSNR < 8dB, BER > 5×10⁻⁵, Power < -20dBm. Action: Reroute immediately, dispatch repair crew.
2. GENERATOR_FAILURE: Power infrastructure fails. OSNR drops below 10dB. Action: Reroute traffic, check backup generators.
3. HARMATTAN_DUST: Dust reduces OSNR ~2dB, affects Kano/Abuja Nov–Feb. Action: Clean connectors, monitor.
4. RAIN_ATTENUATION: Heavy rain reduces power 2.5–6dB in Lagos/PH Apr–Oct. Action: Monitor, no immediate action needed.
5. PEAK_CONGESTION: Lagos evening hours, high traffic causes signal degradation. Action: Load balance, prioritize critical traffic.

KEY METRICS:
• OSNR (Optical Signal-to-Noise Ratio): Measures signal clarity in dB. Higher is better. Normal: ≥ 19dB.
• BER (Bit Error Rate): Fraction of corrupted bits. Lower is better. Normal: ≤ 1×10⁻⁶.
• Latency: Signal propagation delay in ms. Normal: ≤ 150ms.
• Optical Power: Signal strength in dBm. Normal range: -20 to +3 dBm.

DASHBOARD FEATURES:
• Run Pipeline: Generates 50–1000 telemetry samples for a city with season-specific degradation
• Diagnose Row: Analyzes a specific telemetry record for faults
• Fault Injection: Simulates fibre cuts, generator failures, harmattan, rain, congestion
• Nexus Chat: AI-powered assistant (that's me!) for technical and simple explanations
• Digital Twin: Live network topology visualization
• NCC Compliance: Automated compliance scoring
• 4-Line Summary: Auto-generated network situation report
• State Distribution: Pie chart showing Normal/Degrading/Critical breakdown
• OSNR Trend: Line chart tracking signal quality over rows
• Complaint System: User-to-agent messaging for support tickets

DASHBOARD SECTIONS:
• Live Metrics: Real-time avg OSNR, BER, Latency, Anomaly count
• State Distribution: Pie chart of Normal/Degrading/Critical
• OSNR Trend: Line chart of OSNR over last 15 rows
• NCC QOS Compliance: OSNR%, BER%, Latency%, Overall status
• Nigerian Fault Event Simulator: Click buttons to inject faults
• Network Summary: AI-generated 4-line situation report
• Diagnosis Output: LLM-powered root cause analysis with confidence
• Telemetry Data: Full table of all generated records

COMPLIANCE SCORING:
• OSNR Compliance %: Percentage of records meeting NCC OSNR threshold
• BER Compliance %: Percentage of records meeting NCC BER threshold
• Latency Compliance %: Percentage of records within 150ms
• Overall Status: COMPLIANT if all ≥ 80%, NON-COMPLIANT otherwise

USER ROLES:
• Superadmin: Full access, user management, activity monitoring
• User: Dashboard access, chat, complaints, profile management

PROFILE FEATURES:
• Theme toggle (dark/light)
• Avatar with custom colour (sets dashboard accent colour)
• Display name
• Telegram/WhatsApp contact for notifications
• Avatar photo upload

NOTIFICATIONS:
• Telegram alerts via Bot API for incident notifications
• WhatsApp alerts via Business API
• Daily network summaries sent to saved contacts
• Incident alerts with severity, city, and recommended actions

TECHNICAL STACK:
• Backend: Python, FastAPI, Uvicorn
• ML: scikit-learn Isolation Forest for anomaly detection
• LLM: Ollama (local) with llama3.2:1b base, nexus-chat and swift-fhs custom models
• Database: SQLite for profiles, complaints, logs
• Frontend: Vanilla JS, Chart.js, CSS dark/light themes
• Auth: JWT (python-jose + passlib/bcrypt)
"""


def _check_ollama() -> bool:
    """Check if Ollama is reachable."""
    try:
        r = _requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _call_ollama(prompt: str, model: str) -> str | None:
    """Call Ollama with non-streaming mode for maximum reliability."""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 2048},
        }
        r = _requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            reply = data.get("response", "").strip()
            if reply:
                return reply
        return None
    except Exception as e:
        _trace(f"  _call_ollama({model}) failed: {e}")
        return None


def _build_prompt(user_message: str, context: dict | None, mode: str) -> str:
    """Build a comprehensive prompt with system instructions, lexicon, context, and user question."""
    parts = [
        "You are Nexus, a friendly, knowledgeable AI assistant for OASIS-X — a Nigerian fibre fault monitoring system.",
        "Always respond in natural, conversational English sentences. Never output JSON or structured data.",
        f"Current mode: {mode}.",
    ]

    if mode == "technical":
        parts.append("Use precise dB values, NCC thresholds, and technical terms. Be specific with numbers.")
    else:
        parts.append("Use plain language, everyday analogies. Avoid jargon. Be accessible to non-technical users.")

    parts.append(LEXICON)

    if context:
        ctx_lines = []
        s = context.get("summary") or {}
        if s.get("city"):
            ctx_lines.append(f"Latest pipeline: {s.get('total_records',0)} records in {s['city']} ({s.get('season','?')} season).")
            d = s.get("state_distribution", {})
            ctx_lines.append(f"State breakdown: {d.get('NORMAL',0)} normal, {d.get('DEGRADING',0)} degrading, {d.get('CRITICAL',0)} critical.")
        if context.get("diagnosis"):
            dx = context["diagnosis"]
            ctx_lines.append(f"Latest diagnosis: {dx.get('diagnosis','')} (source: {dx.get('source','')}).")
        if context.get("ncc"):
            n = context["ncc"]
            ctx_lines.append(f"NCC: OSNR {n.get('osnr_compliance_pct','?')}%, BER {n.get('ber_compliance_pct','?')}%, Latency {n.get('latency_compliance_pct','?')}% — {n.get('overall_status','?')}.")
        if ctx_lines:
            parts.append("Current dashboard data:\n" + "\n".join(ctx_lines))

    parts.append(f"User: {user_message}")
    parts.append("Respond helpfully and conversationally. If greeting, greet warmly first then offer help.")

    return "\n\n".join(parts)


def chat_with_llm(user_message: str, context: dict | None = None, mode: str = "technical") -> dict:
    """Main chat entry point. Handles greetings, LLM calls, and fallbacks."""
    _trace(f"ENTER chat_with_llm  mode='{mode}'  msg='{user_message[:80]}'")

    # Step 1: Check for greetings (rule-based, instant, no LLM needed)
    greeting_reply = _is_greeting(user_message)
    if greeting_reply:
        _trace("  Greeting detected — returning rule-based response")
        return {"reply": greeting_reply, "source": "greeting"}

    # Step 2: Check Ollama
    if not _check_ollama():
        _trace("  Ollama not reachable — using rule-based fallback")
        return {"reply": _rule_fallback(user_message, mode), "source": "offline"}

    # Step 3: Try LLM models
    prompt = _build_prompt(user_message, context, mode)
    _trace(f"  Prompt built: {len(prompt)} chars, trying models: {MODELS_TO_TRY}")

    for model in MODELS_TO_TRY:
        _trace(f"  Trying: {model}")
        reply = _call_ollama(prompt, model)
        if reply and len(reply) > 5:
            _trace(f"  SUCCESS with {model} — {len(reply)} chars")
            return {"reply": reply, "source": "llm"}
        _trace(f"  {model} returned empty/short response")

    # Step 4: All models failed — rule-based fallback
    _trace("  All models failed — rule-based fallback")
    return {"reply": _rule_fallback(user_message, mode), "source": "fallback"}


def _rule_fallback(message: str, mode: str) -> str:
    """Rule-based responses when LLM is unavailable."""
    msg = message.lower().strip()

    # Common questions
    if any(w in msg for w in ["what is osnr", "what's osnr", "explain osnr", "tell me about osnr"]):
        if mode == "technical":
            return ("OSNR (Optical Signal-to-Noise Ratio) measures signal clarity in dB. "
                    "NCC thresholds: Lagos/Abuja require ≥ 15dB, Port Harcourt/Kano ≥ 14dB. "
                    "Normal operation is ≥ 19dB. Below 15dB is CRITICAL.")
        return ("OSNR is like the clarity of a radio signal — it tells us how clean the fibre optic signal is. "
                "Higher numbers mean better quality. Think of it as signal-to-noise ratio. "
                "Nigerian regulations require at least 14–15 dB depending on the city.")

    if any(w in msg for w in ["what is ber", "what's ber", "explain ber", "bit error"]):
        if mode == "technical":
            return ("BER (Bit Error Rate) is the fraction of corrupted bits. "
                    "NCC max: 1×10⁻⁵ for Lagos/Abuja, 1.5×10⁻⁵ for PH/Kano. "
                    "Normal: ≤ 1×10⁻⁶. Above 1×10⁻⁵ is CRITICAL.")
        return (" BER is how many bits get corrupted during transmission — like typos in a message. "
                "Lower is better. Nigerian rules say it should be below 0.001% for reliable service.")

    if any(w in msg for w in ["what is latency", "explain latency", "how fast"]):
        return ("Latency is the time it takes for data to travel through the fibre. "
                "NCC requires it under 150 milliseconds. Think of it as the delay — "
                "like how long it takes for your voice to reach someone on a phone call.")

    if any(w in msg for w in ["fibre cut", "fiber cut", "cable cut", "physical cut"]):
        return ("A fibre cut is when the physical cable is broken — usually from construction or accidents. "
                "It causes OSNR to drop below 8dB and BER to spike above 5×10⁻⁵. "
                "OASIS-X automatically reroutes traffic and alerts repair crews.")

    if any(w in msg for w in ["generator fail", "power fail", "backup gen"]):
        return ("Generator failure means the power infrastructure supporting the fibre nodes has failed. "
                "This causes OSNR to drop below 10dB. The system reroutes traffic to backup paths "
                "and alerts technicians to check backup generators.")

    if any(w in msg for w in ["harmattan", "dust", "harmattan dust"]):
        return ("Harmattan is a dry, dusty wind from the Sahara that blows across Nigeria Nov–Feb. "
                "It deposits dust on fibre connectors, reducing OSNR by about 2dB, especially in Kano and Abuja. "
                "Solution: clean the connectors and monitor closely.")

    if any(w in msg for w in ["rain", "rain attenuation", "monsoon"]):
        return ("Heavy rain absorbs and scatters optical signals, reducing power by 2.5–6dB. "
                "This mainly affects Lagos and Port Harcourt during the rainy season (Apr–Oct). "
                "The system monitors this automatically and adjusts thresholds.")

    if any(w in msg for w in ["ncc", "compliance", "nigerian communications"]):
        return ("The Nigerian Communications Commission (NCC) sets Quality of Service (QoS) standards for ISPs. "
                "OASIS-X automatically checks every telemetry record against NCC thresholds for OSNR, BER, "
                "and latency, and reports compliance percentages.")

    if any(w in msg for w in ["what is oasis", "what's oasis", "tell me about oasis", "about oasis-x", "what does oasis"]):
        return ("OASIS-X stands for Smart Waveform Integrated Fibre-optic Transmission — Fault Healing System. "
                "It's a real-time autonomous fibre monitoring dashboard for Nigerian networks. "
                "It detects faults with ML, diagnoses them with AI, and can auto-heal by rerouting traffic.")

    if any(w in msg for w in ["who made", "who built", "who developed", "creator", "author"]):
        return ("OASIS-X was developed for Nigerian optical fibre networks. "
                "It's built to handle conditions from harmattan dust in Kano to monsoon rains in Port Harcourt. "
                "The project is hosted at github.com/jaycode100-sys/OASIS-X.")

    if any(w in msg for w in ["anomal", "anomaly detect", "isolation forest"]):
        return ("OASIS-X uses an Isolation Forest algorithm for anomaly detection. "
                "It learns normal telemetry patterns and flags records that deviate significantly. "
                "Anomalies are shown in the Live Metrics panel with a count of flagged records.")

    if any(w in msg for w in ["digital twin", "topology", "network map"]):
        return ("The Digital Twin feature provides real-time visualization of the fibre network topology. "
                "You can see cable routes, node health, and active fault propagation across cities.")

    if any(w in msg for w in ["chat mode", "technical mode", "simple mode"]):
        return ("Nexus has two modes: Technical mode uses precise dB values and NCC thresholds. "
                "Simple mode uses plain language and everyday analogies. Toggle with the switch in the chat header.")

    if any(w in msg for w in ["pipeline", "run pipeline", "generate data"]):
        return ("The Run Pipeline button generates 50–1000 telemetry samples for the selected city. "
                "It simulates real fibre conditions with season-specific degradation, "
                "then shows results in charts, compliance scores, and state distribution.")

    if any(w in msg for w in ["season", "which season", "current season"]):
        return ("OASIS-X tracks four seasons: Harmattan (Nov–Feb, dust), Rainy (Apr–Oct, attenuation), "
                "Dry (Jul–Sep, normal), and Normal (Oct, transition). "
                "You can override the season with the Season Override buttons in the sidebar.")

    if any(w in msg for w in ["diagnose", "diagnosis", "fault analysis"]):
        return ("Diagnosis analyzes a specific telemetry row for faults. "
                "It uses the swift-fhs LLM model (with rule-engine fallback) to identify root cause, "
                "confidence level, NCC compliance, and urgency. Click 'Diagnose' after running a pipeline.")

    if any(w in msg for w in ["notification", "alert", "telegram", "whatsapp", "send summary"]):
        return ("OASIS-X can send network summaries and incident alerts via Telegram and WhatsApp. "
                "Save your contact info in Profile → Contact Information, then click 'Send to Phone' "
                "in the Network Summary section. Alerts require a Telegram bot token or WhatsApp Business API.")

    if any(w in msg for w in ["hello", "hi", "hey", "yo", "how are"]):
        return ("Hey there! 👋 I'm Nexus, your AI network assistant. "
                "Ask me about fibre telemetry, NCC compliance, fault diagnosis, or anything about the dashboard!")

    # Generic fallback
    if mode == "technical":
        return (f"I can help with that. OASIS-X monitors fibre networks across 4 Nigerian cities "
                f"(Lagos, Abuja, Port Harcourt, Kano) using OSNR, BER, and latency metrics against NCC standards. "
                f"Try asking about specific metrics, fault types, compliance, or dashboard features.")
    return (f"I'd be happy to help! OASIS-X is a fibre network monitoring system for Nigeria. "
            f"Ask me about the network status, what the metrics mean, how faults are handled, "
            f"or anything about the dashboard. I'm here to help!")


def diagnose_ollama() -> dict:
    """Comprehensive Ollama diagnostics."""
    results = {
        "reachable": False, "models": [], "tests": {},
        "errors": [], "fix_commands": [],
    }

    if not _check_ollama():
        results["errors"].append("Ollama is not reachable")
        results["fix_commands"] = [
            "1. Start Ollama: ollama serve",
            "2. Pull model: ollama pull llama3.2:1b",
            "3. Create chat model: ollama create nexus-chat -f models/.ollama/ChatModelfile",
        ]
        return results

    results["reachable"] = True

    # List models
    try:
        r = _requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        models = r.json().get("models", [])
        results["models"] = [m["name"] for m in models]
    except Exception:
        pass

    # Test each model
    for model in MODELS_TO_TRY:
        key = model.replace(".", "_").replace(":", "_")
        if any(m == model or m.startswith(model + ":") for m in results["models"]):
            try:
                r = _requests.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": model, "prompt": "Say OK", "stream": False, "options": {"num_ctx": 512}},
                    timeout=30,
                )
                data = r.json() if r.status_code == 200 else {}
                results["tests"][key] = {
                    "status": r.status_code,
                    "passed": r.status_code == 200,
                    "response": data.get("response", "")[:100],
                }
            except Exception as e:
                results["tests"][key] = {"error": str(e), "passed": False}
                results["errors"].append(f"{model}: {e}")
        else:
            results["tests"][key] = {"error": "not installed", "passed": False}

    if any(not t.get("passed") for t in results["tests"].values()):
        results["fix_commands"] = [
            "1. Restart Ollama: ollama serve",
            "2. ollama pull llama3.2:1b",
            "3. ollama create nexus-chat -f models/.ollama/ChatModelfile",
            "4. ollama create swift-fhs -f models/.ollama/Modelfile",
        ]

    return results
