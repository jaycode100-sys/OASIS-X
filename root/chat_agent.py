import json, logging, os, http.client, sys
from root.llm_agent import OLLAMA_BASE_URL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)

_TRACE_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chat_trace.log")

def _trace(msg: str):
    """Console log for diagnostic tracing — prints to stdout AND writes to file."""
    print(f"[CHAT_TRACE] {msg}", flush=True)
    logger.debug(msg)
    try:
        with open(_TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass

CHAT_MODEL = "nexus-chat"
_chat_available: bool | None = None

SYSTEM = """You are Nexus, a helpful network assistant for OASIS-X, a Nigerian fibre fault monitoring system. Always respond in natural sentences, never in JSON.

The NCC (Nigerian Communications Commission) sets the quality standards. OSNR measures signal clarity in dB. The minimum OSNR is 15 dB for Lagos and Abuja, and 14 dB for Port Harcourt and Kano. BER is the bit error rate and must stay below 1 times 10 to the minus 5 for Lagos and Abuja, and below 1.5 times 10 to the minus 5 for Port Harcourt and Kano. Latency must be under 150 milliseconds. Optical power normally ranges from minus 20 to plus 3 dBm.

The network has three states: NORMAL when everything is within limits, DEGRADING when metrics approach thresholds, and CRITICAL when limits are breached. There are four cities: Lagos, Abuja, Port Harcourt, and Kano. The seasons are harmattan from November to February, rainy from March to June, dry from July to September, and normal in October.

The five fault types are: fiber_cut where the cable is physically broken, generator_failure where power infrastructure fails, harmattan_degradation where dust reduces OSNR, rain_attenuation where heavy rain reduces power, and peak_congestion during Lagos evening hours.

In technical mode, use precise numbers and NCC threshold values. In simple mode, use plain language and everyday analogies. Be concise and reply in 2 to 4 sentences. Never output JSON or any structured data format."""


def reset_chat_cache():
    global _chat_available
    _chat_available = None


def _check_ollama_reachable() -> bool:
    """Quick connectivity check — always re-probes so that a temporarily
       unreachable Ollama doesn't permanently disable chat."""
    try:
        host, port = _ollama_url()
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/api/tags")
        resp = conn.getresponse()
        resp.read()  # drain
        conn.close()
        ok = resp.status == 200
        if not ok:
            logger.warning(f"Ollama returned status {resp.status}")
        return ok
    except Exception as e:
        logger.warning(f"Ollama not reachable at {OLLAMA_BASE_URL} ({e})")
        return False


def _ollama_url() -> tuple:
    """Parse OLLAMA_BASE_URL into (host, port) tuple for http.client."""
    from urllib.parse import urlparse
    u = urlparse(OLLAMA_BASE_URL)
    host = u.hostname or "localhost"
    port = u.port or 11434
    return host, port


def _call_generate(prompt: str, model: str) -> str | None:
    """Call Ollama /api/generate using **streaming mode** so that individual
       tokens arrive continuously and we never hit a socket-level timeout
       waiting for the complete response.

       Uses a per-token idle timeout (TOKEN_IDLE_TIMEOUT) so that a truly
       stuck model is detected within seconds rather than waiting the full
       OLLAMA_TIMEOUT.

       No 'system' param — system text is baked into the prompt to match
       the working diagnosis pattern and avoid an Ollama Windows bug where
       a separate 'system' field triggers spurious image-processing errors."""

    TOKEN_IDLE_TIMEOUT = 90  # seconds to wait for each new token chunk

    _trace(f"ENTER _call_generate(model='{model}')  prompt_len={len(prompt)}")
    conn = None
    try:
        host, port = _ollama_url()
        _trace(f"  Ollama URL: {host}:{port}")
        conn = http.client.HTTPConnection(
            host, port, timeout=OLLAMA_TIMEOUT
        )
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.3, "num_ctx": 4096},
        })
        _trace(f"  Payload keys: model={model}, stream=True, options={{temp:0.3, ctx:4096}}")
        _trace(f"  Payload size: {len(payload)} bytes  (NO 'system' field)")
        conn.request(
            "POST", "/api/generate",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        _trace(f"  Request sent (streaming), waiting for first token (timeout={OLLAMA_TIMEOUT}s)...")
        resp = conn.getresponse()
        _trace(f"  HTTP status: {resp.status} {resp.reason}")

        if resp.status != 200:
            body = resp.read().decode()
            logger.warning(
                f"Ollama HTTP {resp.status} for '{model}': {body[:500]}"
            )
            _trace(f"  NON-200 response — returning None")
            return None

        # ── Stream token chunks ──────────────────────────────────────
        # Ollama streams one JSON object per line: {"response":"token","done":false}
        # The final line has "done":true. We set a per-read idle timeout
        # so a stuck model is caught quickly.
        parts = []
        buf = b""
        conn.sock.settimeout(TOKEN_IDLE_TIMEOUT)
        done = False

        while not done:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk
            # Process complete lines
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                token = obj.get("response", "")
                if token:
                    parts.append(token)
                if obj.get("done", False):
                    done = True
                    break

        # Process any remaining data in the buffer
        if buf.strip():
            try:
                obj = json.loads(buf.strip().decode())
                token = obj.get("response", "")
                if token:
                    parts.append(token)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        reply = "".join(parts).strip()
        _trace(f"  Streamed reply: {len(reply)} chars, first 120='{reply[:120]}'")
        if not reply:
            _trace(f"  WARNING: empty reply from model '{model}'")
        _trace(f"EXIT _call_generate -> OK ({len(reply)} chars)")
        return reply if reply else None
    except Exception as e:
        logger.warning(f"Ollama call to '{model}' failed: {e}")
        _trace(f"  EXCEPTION: {e}")
        return None
    finally:
        # Always close the connection to free Ollama resources
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _build_prompt(user_message, context, mode):
    """Build a llama3.2 chat-template prompt (system+user wrapped in
       role markers) so the model responds conversationally rather
       than in JSON."""
    _trace(f"BUILD PROMPT: mode={mode}, context_summary_city={context.get('summary',{}).get('city','?') if context else 'None'}")
    parts = [SYSTEM + f"\nMode: {mode}."]
    if context:
        lines = []
        s = context.get("summary") or {}
        if s.get("city"):
            lines.append(
                f"Latest pipeline run: {s.get('total_records',0)} records "
                f"in {s['city']} ({s.get('season','?')} season)."
            )
            d = s.get("state_distribution", {})
            lines.append(
                f"Network state breakdown: {d.get('NORMAL',0)} normal, "
                f"{d.get('DEGRADING',0)} degrading, "
                f"{d.get('CRITICAL',0)} critical."
            )
        if context.get("diagnosis"):
            dx = context["diagnosis"]
            lines.append(
                f"Latest fault analysis: {dx.get('diagnosis','')} "
                f"(source: {dx.get('source','')})."
            )
        if context.get("ncc"):
            n = context["ncc"]
            lines.append(
                f"NCC compliance: {n.get('osnr_compliance_pct','?')}% OSNR, "
                f"{n.get('ber_compliance_pct','?')}% BER, "
                f"{n.get('latency_compliance_pct','?')}% latency — "
                f"overall {n.get('overall_status','?')}."
            )
        if lines:
            parts.append("Current dashboard:\n" + "\n".join(lines))
    parts.append(f"User question: {user_message}")

    # Wrap in llama3.2 chat template for conversational response
    system_text = "\n".join(parts[:-1])
    user_text = parts[-1].replace("User question: ", "", 1)
    _trace(f"  System text portion: {len(system_text)} chars")
    _trace(f"  User text: '{user_text[:100]}...' ({len(user_text)} chars)")
    return (
        f"<|start_header_id|>system<|end_header_id|>\n\n"
        f"{system_text}<|eot_id|>\n"
        f"<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_text}<|eot_id|>\n"
        f"<|start_header_id|>assistant<|end_header_id|>"
    )


def diagnose_ollama() -> dict:
    """Comprehensive Ollama diagnostics — tests connectivity, lists models,
    and sends a minimal prompt to each available model."""
    import requests
    results = {
        "reachable": False, "models": [], "model_details": [],
        "tests": {}, "errors": [], "cli_version": None,
        "fix_commands": [],
    }

    # 1. Check Ollama reachability
    try:
        tags_resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if tags_resp.status_code == 200:
            results["reachable"] = True
            models_data = tags_resp.json().get("models", [])
            results["models"] = [m["name"] for m in models_data]
            results["model_details"] = [
                {k: m.get(k) for k in ("name","modified_at","size","digest")}
                for m in models_data
            ]
        else:
            results["errors"].append(f"/api/tags returned HTTP {tags_resp.status_code}")
    except Exception as e:
        results["errors"].append(f"Ollama unreachable: {e}")
        return results  # can't test further

    # 2. Test each model with a minimal prompt (matching our /api/generate pattern)
    test_prompt = "You are a helpful assistant.\n\nUser: say OK"
    for model in [CHAT_MODEL, "llama3.2:1b", "swift-fhs"]:
        test_key = model.replace(".", "_").replace(":", "_")
        if any(m == model or m.startswith(model + ":") for m in results["models"]):
            try:
                host, port = _ollama_url()
                conn = http.client.HTTPConnection(
                    host, port, timeout=60
                )
                payload = json.dumps({
                    "model": model,
                    "prompt": test_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_ctx": 1024},
                })
                conn.request(
                    "POST", "/api/generate",
                    body=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                body = resp.read().decode()
                entry = {
                    "status": resp.status,
                    "body_preview": body[:300],
                    "passed": resp.status == 200,
                }
                if resp.status == 200:
                    try:
                        data = json.loads(body)
                        entry["response"] = data.get("response", "")[:100]
                    except Exception:
                        pass
                else:
                    results["errors"].append(
                        f"{model}: HTTP {resp.status} — {body[:150]}"
                    )
                results["tests"][test_key] = entry
            except Exception as e:
                results["tests"][test_key] = {"error": str(e), "passed": False}
                results["errors"].append(f"{model}: {e}")
        else:
            results["tests"][test_key] = {"error": "model not found", "passed": False}
            results["errors"].append(f"{model}: not found in Ollama")

    # 3. Try check with ollama CLI
    try:
        import subprocess
        cli = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=5
        )
        results["cli_version"] = cli.stdout.strip() or cli.stderr.strip()
    except Exception as e:
        results["cli_version"] = f"not available: {e}"

    # 4. Build fix commands
    any_failed = any(
        not t.get("passed", False) for t in results["tests"].values()
    )
    if any_failed:
        results["fix_commands"] = [
            "1. Restart Ollama completely:",
            "   - Close Ollama from system tray",
            "   - Run: ollama serve",
            "",
            "2. Re-pull the base model:",
            "   ollama pull llama3.2:1b",
            "",
            "3. Recreate nexus-chat:",
            "   ollama create nexus-chat -f models/.ollama/ChatModelfile",
            "",
            "4. If still failing, update Ollama:",
            "   https://ollama.com/download",
        ]

    return results


def chat_with_llm(user_message, context=None, mode="technical"):
    _trace(f"ENTER chat_with_llm()  mode='{mode}'  msg='{user_message}'  context_keys={list(context.keys()) if context else 'None'}")
    
    if not _check_ollama_reachable():
        _trace("  Ollama not reachable — returning offline message")
        return {
            "reply": "Nexus AI is offline. Make sure Ollama is running "
                     "(ollama serve), then:\n\n"
                     "  ollama pull llama3.2:1b\n"
                     "  ollama create nexus-chat -f models/.ollama/ChatModelfile\n\n"
                     "The rule-based diagnosis engine still works for fault analysis.",
            "source": "offline",
        }

    prompt = _build_prompt(user_message, context, mode)
    _trace(f"  Built prompt: {len(prompt)} chars")
    _trace(f"  Prompt starts: {prompt[:150]}")
    _trace(f"  Prompt ends: {prompt[-150:]}")

    models_to_try = [CHAT_MODEL, "llama3.2:1b", "swift-fhs"]
    last_error = None
    for model in models_to_try:
        _trace(f"  Trying model: '{model}'")
        reply = _call_generate(prompt, model)
        if reply is not None:
            _trace(f"  Model '{model}' succeeded — returning reply")
            return {"reply": reply, "source": "llm"}
        _trace(f"  Model '{model}' returned None — trying next")
        last_error = model

    _trace(f"  All models exhausted — returning error message")
    return {
        "reply": f"All Ollama models failed (tried: {', '.join(models_to_try)}). "
                 f"Run this in your terminal to fix the models:\n\n"
                 f"  ollama pull llama3.2:1b\n"
                 f"  ollama create nexus-chat -f models/.ollama/ChatModelfile\n\n"
                 f"Last model tried: {last_error}",
        "source": "error",
    }
