"""Tests for decision engine."""
from root.decision_engine import classify_state


def test_classify_normal():
    row = {"osnr_db": 28, "ber": 1e-6, "latency_ms": 5, "qos_score": 98}
    assert classify_state(row) == "NORMAL"


def test_classify_degrading():
    row = {"osnr_db": 17, "ber": 5e-6, "latency_ms": 15, "qos_score": 65}
    assert classify_state(row) == "DEGRADING"


def test_classify_critical():
    row = {"osnr_db": 12, "ber": 5e-4, "latency_ms": 40, "qos_score": 25}
    assert classify_state(row) == "CRITICAL"
