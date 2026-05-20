import numpy as np
import pandas as pd
import os

# ── NCC-Realistic Baseline Parameters ─────────────────────────────────────────
# Derived from NCC QoS published reports and typical Nigerian ISP/telco metrics.

NCC_OSNR_BASELINE_DB = 20.5          # Slightly lower than international 22 dB norm
NCC_BER_THRESHOLD = 1e-6             # NCC minimum acceptable BER
NCC_LATENCY_BASELINE_MS = 12.0       # Realistic Nigerian backbone latency
NCC_POWER_BASELINE_DBM = -1.5        # Slightly attenuated baseline power


# ── Time-of-Day Pattern ────────────────────────────────────────────────────────
# Based on Lagos/Nigeria usage patterns: peak 19:00–22:00, trough 02:00–05:00

def _time_of_day_factor(hour: int) -> float:
    """
    Returns a congestion multiplier for latency and BER based on the hour of
    day (0-23), modelling peak evening usage in Lagos.

    Returns a value in roughly [0.7, 1.6] — 1.0 = normal load.
    """
    if 19 <= hour <= 22:    # Peak: heavy evening streaming / social media
        return 1.6
    elif 7 <= hour <= 9:    # Morning rush
        return 1.3
    elif 12 <= hour <= 14:  # Lunchtime bump
        return 1.15
    elif 2 <= hour <= 5:    # Deep night: minimal traffic
        return 0.7
    return 1.0


# ── Seasonal Environmental Effects ────────────────────────────────────────────

def _harmattan_attenuation(step: int, n: int, season: str) -> float:
    """
    Harmattan dust (Nov–Feb) causes gradual OSNR degradation on exposed
    microwave and fibre links due to particulate accumulation on connectors.

    Returns an OSNR offset (negative = loss) in dB.
    """
    if season != "harmattan":
        return 0.0
    # Progressive dust build-up over the season — peaks mid-season
    progress = step / n
    return -(0.5 + 1.5 * np.sin(np.pi * progress))   # up to -2 dB


def _rain_attenuation(step: int, rng: np.random.Generator, season: str) -> tuple[float, float]:
    """
    Heavy rain (Apr–Oct rainy season) causes sudden optical power drops and
    BER spikes. Returns (power_offset_dBm, ber_multiplier).
    """
    if season != "rainy":
        return 0.0, 1.0

    # Random heavy-rain events — ~15% probability per step
    if rng.random() < 0.15:
        power_drop = rng.uniform(-6.0, -2.5)    # -2.5 to -6 dBm sudden drop
        ber_mult = rng.uniform(3.0, 8.0)         # BER spikes 3-8x during rain
        return power_drop, ber_mult
    return 0.0, 1.0


# ── Generator Failure Events ───────────────────────────────────────────────────

def _inject_generator_failure(
    osnr: np.ndarray,
    ber: np.ndarray,
    power: np.ndarray,
    events: list,
    start: int,
    duration: int = 18,
):
    """
    Simulate a generator failure:
    - Sudden OSNR collapse (site goes dark) for `duration` steps
    - Gradual recovery curve as generator restarts

    Modelled on NCC-reported telco generator outage durations (15–30 min avg).
    """
    end = min(start + duration, len(osnr))
    collapse = min(start + 3, end)        # takes ~3 steps to fully collapse

    # Collapse phase
    for i in range(start, collapse):
        frac = (i - start + 1) / 3
        osnr[i] -= frac * 12.0
        power[i] -= frac * 15.0
        ber[i] *= 1 + frac * 40

    # Dark / critical phase
    for i in range(collapse, end - 5):
        osnr[i] = max(osnr[i] - 13.0, 3.0)
        power[i] = -28.0
        ber[i] *= 50

    # Recovery ramp
    recovery_start = end - 5
    for i in range(recovery_start, end):
        ramp = (i - recovery_start + 1) / 5
        osnr[i] += ramp * 10.0
        power[i] = -28.0 + ramp * 26.5
        ber[i] = max(ber[i] / (ramp * 30 + 1), NCC_BER_THRESHOLD * 5)

    events.append({"start": start, "end": end, "type": "GENERATOR_FAILURE"})


# ── Main Simulator ─────────────────────────────────────────────────────────────

def generate_network_data(
    n: int = 200,
    seed: int = 42,
    season: str = "harmattan",
    city: str = "Lagos",
    inject_generator_failure: bool = True,
) -> pd.DataFrame:
    """
    Generate realistic Nigerian optical network telemetry with environmental
    and infrastructure fault patterns.

    Args:
        n:                       Number of telemetry time steps.
        seed:                    Random seed for reproducibility.
        season:                  Environmental season context.
                                 Options: "harmattan" | "rainy" | "dry" | "normal"
        city:                    Nigerian city context (affects baseline parameters).
                                 Options: "Lagos" | "Abuja" | "PortHarcourt" | "Kano"
        inject_generator_failure: Whether to inject a generator failure event.

    Returns:
        Enriched DataFrame with columns including: time, osnr_db, ber,
        power_dbm, latency_ms, event, time_of_day, season,
        environmental_factor, fault_cause.
    """
    rng = np.random.default_rng(seed)

    # Per-city baseline offsets (NCC QoS data shows inter-city variation)
    city_profiles = {
        "Lagos":        {"osnr_offset": 0.0,  "latency_offset": 0.0},
        "Abuja":        {"osnr_offset": 0.5,  "latency_offset": -1.0},
        "PortHarcourt": {"osnr_offset": -0.3, "latency_offset": 2.0},   # humidity, oil activity
        "Kano":         {"osnr_offset": -0.8, "latency_offset": 1.5},   # harmattan worst here
    }
    profile = city_profiles.get(city, city_profiles["Lagos"])

    time = np.arange(n)

    # Assign a simulated hour-of-day for each step (cycles through 24h)
    hours = (time % 48) // 2     # each step = 30 min; 48 steps per day

    # ── Baseline signals using NCC-realistic parameters ──
    osnr = NCC_OSNR_BASELINE_DB + profile["osnr_offset"] + rng.normal(0, 0.8, n)
    ber = NCC_BER_THRESHOLD + rng.normal(0, NCC_BER_THRESHOLD * 0.1, n)
    ber = np.clip(ber, 0, None)
    power = NCC_POWER_BASELINE_DBM + rng.normal(0, 0.5, n)
    latency = NCC_LATENCY_BASELINE_MS + profile["latency_offset"] + rng.normal(0, 2.0, n)

    # ── Time-of-day congestion modulation ──
    tod_factors = np.array([_time_of_day_factor(h) for h in hours])
    latency *= tod_factors
    ber *= (0.8 + 0.4 * tod_factors)    # BER rises slightly under congestion

    # ── Seasonal effects ──
    env_factor = np.zeros(n)
    for i in range(n):
        harmattan_offset = _harmattan_attenuation(i, n, season)
        rain_power_offset, rain_ber_mult = _rain_attenuation(i, rng, season)

        osnr[i] += harmattan_offset
        power[i] += rain_power_offset
        ber[i] *= rain_ber_mult

        env_factor[i] = abs(harmattan_offset) + abs(rain_power_offset) / 3

    ber = np.clip(ber, 0, None)

    # ── Gradual fibre degradation (amplifier aging / bending) ──
    degradation_start = 120
    for i in range(degradation_start, n):
        deg = (i - degradation_start) * 0.12
        osnr[i] -= deg
        ber[i] += deg * 2e-7
        power[i] -= deg * 0.08
    ber = np.clip(ber, 0, None)

    # ── Sudden fibre cut ──
    cut_point = 165
    if cut_point < n:
        osnr[cut_point:] = np.clip(osnr[cut_point:], None, 8.0)
        ber[cut_point:] *= 50
        power[cut_point:] = -25.0

    # ── Generator failure injection ──
    injected_events = []
    if inject_generator_failure:
        gen_fail_start = 75    # mid-normal period (simulates a random grid outage)
        _inject_generator_failure(osnr, ber, power, injected_events,
                                  start=gen_fail_start, duration=18)
        ber = np.clip(ber, 0, None)

    # ── Assemble DataFrame ──
    fault_cause = np.full(n, "NONE", dtype=object)
    event = np.full(n, "NORMAL", dtype=object)

    event[degradation_start:cut_point] = "DEGRADING"
    fault_cause[degradation_start:cut_point] = "FIBRE_AGING"

    event[cut_point:] = "FIBER_CUT"
    fault_cause[cut_point:] = "PHYSICAL_CUT"

    for ev in injected_events:
        s, e = ev["start"], ev["end"]
        event[s:e] = "GENERATOR_FAILURE"
        fault_cause[s:e] = "POWER_INFRASTRUCTURE"

    if season == "harmattan":
        fault_cause[env_factor > 0.8] = "HARMATTAN_DUST"
    elif season == "rainy":
        fault_cause[(env_factor > 0.5) & (event == "NORMAL")] = "RAIN_ATTENUATION"

    df = pd.DataFrame({
        "time": time,
        "hour_of_day": hours,
        "osnr_db": np.round(osnr, 3),
        "ber": ber,
        "power_dbm": np.round(power, 3),
        "latency_ms": np.round(latency, 3),
        "event": event,
        "fault_cause": fault_cause,
        "environmental_factor": np.round(env_factor, 4),
        "season": season,
        "city": city,
    })

    # Persist raw logs
    os.makedirs("data", exist_ok=True)
    df.to_csv("data/raw_fibre_logs.csv", index=False)

    print(f"[{city} | {season}] Generated {n} telemetry records. "
          f"Fault injected at t={cut_point}. "
          f"Generator failure: {'Yes (t=' + str(injected_events[0]['start']) + ')' if injected_events else 'No'}")
    return df