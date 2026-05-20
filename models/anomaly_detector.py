import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "anomaly_model.pkl")


def detect_anomalies(df: pd.DataFrame, retrain: bool = False) -> pd.DataFrame:
    """
    Detect anomalies in optical network telemetry using IsolationForest.

    Args:
        df:      Raw telemetry DataFrame (must contain osnr_db, ber, power_dbm, latency_ms).
        retrain: If True, always fit a new model and overwrite the saved one.
                 If False (default), load the saved model when available.

    Returns:
        DataFrame with added columns: osnr_drop, ber_rise, osnr_trend,
        ber_trend, anomaly_score, anomaly_flag.
    """
    df = df.copy()

    # --- Feature engineering ---
    # Use min_periods=1 so rolling windows don't produce NaN on the first rows,
    # avoiding the bias introduced by filling them with 0.
    df["osnr_drop"] = df["osnr_db"].diff().fillna(0)
    df["ber_rise"] = df["ber"].diff().fillna(0)
    df["osnr_trend"] = df["osnr_db"].rolling(window=5, min_periods=1).mean()
    df["ber_trend"] = df["ber"].rolling(window=5, min_periods=1).mean()

    features = df[["osnr_db", "ber", "power_dbm", "latency_ms",
                   "osnr_drop", "ber_rise", "osnr_trend", "ber_trend"]]

    # --- Model: load or train ---
    if not retrain and os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        predictions = model.predict(features)
    else:
        model = IsolationForest(contamination=0.12, random_state=42)
        predictions = model.fit_predict(features)
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        print(f"Anomaly model trained and saved -> {MODEL_PATH}")

    df["anomaly_score"] = predictions
    df["anomaly_flag"] = (df["anomaly_score"] == -1).astype(int)

    return df