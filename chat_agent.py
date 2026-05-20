import logging, os
from root.llm_agent import _check_ollama, OLLAMA_BASE_URL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)

CHAT_MODEL = "nexus-chat"

SYSTEM = """You are Nexus, a helpful network assistant for OASIS-X, a Nigerian fibre fault monitoring system.

Key facts:
- NCC: Nigerian Communications Commission (federal QoS regulator)
- OSNR: signal clarity in dB. NCC min: 15 (Lagos/Abuja), 14 (PH/Kano)
- BER: bit error rate. NCC max: 1e-5 (Lagos/Abuja), 1.5e-5 (PH/Kano)
- Latency: NCC max 150ms. Power: normal -20 to +3 dBm
- States: NORMAL / DEGRADING / CRITICAL
- Cities: Lagos, Abuja, Port Harcourt, Kano
- Seasons: harmattan, rainy, dry, normal
- Faults: fiber_cut, generator_failure, harmattan_degradation, rain_attenuation, peak_congestion

In technical mode: use precise metrics and NCC thresholds.
In simple mode: use plain language and analogies.
Be concise (2-4 sentences)."""


def chat_with_llm(user_message, context=None, mode="technical"):
    if not _check_ollama():
        return {"reply": "Ollama is not available. The LLM agent is offline.", "source": "offline"}

    messages = [{"role": "system", "content": SYSTEM + f"\nMode: {mode}."}]

    if context:
        lines = []
        s = context.get("summary") or {}
        if s.get("city"):
            lines.append(f"Latest run: {s.get('total_records',0)} records, {s['city']}, {s.get('season','?')} season")
            d = s.get("state_distribution", {})
            lines.append(f"States: N={d.get('NORMAL',0)} D={d.get('DEGRADING',0)} C={d.get('CRITICAL',0)}")
        if context.get("diagnosis"):
            dx = context["diagnosis"]
            lines.append(f"Diagnosis: {dx.get('diagnosis','')} ({dx.get('source','')})")
        if context.get("ncc"):
            n = context["ncc"]
            lines.append(f"NCC: {n.get('osnr_compliance_pct','?')}% OSNR, {n.get('ber_compliance_pct','?')}% BER, {n.get('latency_compliance_pct','?')}% latency — {n.get('overall_status','?')}")
        if lines:
            messages.append({"role": "system", "content": "Dashboard:\n" + "\n".join(lines)})

    messages.append({"role": "user", "content": user_message})

    try:
        import requests
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": CHAT_MODEL, "messages": messages, "stream": False,
                  "options": {"temperature": 0.3, "num_ctx": 4096}},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        reply = resp.json().get("message", {}).get("content", "").strip()
        return {"reply": reply, "source": "llm"}
    except Exception as e:
        logger.warning(f"Chat LLM call failed: {e}")
        return {"reply": f"Sorry, I couldn't reach the LLM. Error: {e}", "source": "error"}
