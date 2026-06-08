"""Tests for anomaly detector."""
import pandas as pd
from models.anomaly_detector import detect_anomalies


def test_detect_anomalies_returns_expected_columns():
    df = pd.DataFrame({
        "osnr_db":   [28, 27, 26, 25, 24],
        "ber":       [1e-6, 2e-6, 5e-6, 1e-5, 5e-5],
        "power_dbm": [4, 4, 3, 2, 1],
        "latency_ms":[5, 6, 7, 8, 9],
    })
    result = detect_anomalies(df)
    assert "anomaly_score" in result.columns
    assert "anomaly_flag" in result.columns
