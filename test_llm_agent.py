"""Quick smoke test for the LLM agent (fallback path)."""
import logging
logging.basicConfig(level=logging.WARNING)

from root.llm_agent import get_llm_diagnosis, reset_availability_cache

reset_availability_cache()

test_rows = [
    {"osnr_db": 7.2,  "ber": 4.8e-4, "power_dbm": -25.0, "latency_ms": 14, "state": "CRITICAL",
     "fault_cause": "PHYSICAL_CUT", "anomaly_flag": 1, "city": "Lagos", "season": "harmattan", "hour_of_day": 20},
    {"osnr_db": 16.8, "ber": 3.2e-6, "power_dbm": -3.1,  "latency_ms": 18, "state": "DEGRADING",
     "fault_cause": "HARMATTAN_DUST", "anomaly_flag": 0, "city": "Kano", "season": "harmattan", "hour_of_day": 14},
    {"osnr_db": 21.5, "ber": 8e-7,   "power_dbm": -1.2,  "latency_ms": 13, "state": "NORMAL",
     "fault_cause": "NONE", "anomaly_flag": 0, "city": "Abuja", "season": "rainy", "hour_of_day": 10},
    {"osnr_db": 4.0,  "ber": 1.2e-4, "power_dbm": -28.0, "latency_ms": 12, "state": "CRITICAL",
     "fault_cause": "GENERATOR_FAILURE", "anomaly_flag": 1, "city": "Lagos", "season": "normal", "hour_of_day": 19},
]

for row in test_rows:
    r = get_llm_diagnosis(row)
    assert "diagnosis" in r
    assert "suggestion" in r
    assert "root_cause" in r
    assert "ncc_compliant" in r
    assert "urgency" in r
    assert "source" in r
    assert r["source"] in ("llm", "rule_engine")
    print(f"[{row['state']:10s}] [{r['source']:12s}] urgency={r['urgency']:10s} ncc={str(r['ncc_compliant']):5s} -> {r['diagnosis'][:60]}")

print()
print("ALL LLM AGENT TESTS PASSED")
