import time
import pandas as pd
import os

from models.data_simulator import generate_network_data
from models.anomaly_detector import detect_anomalies
from models.ncc_feed import simulate_ncc_drift, get_current_season
from root.decision_engine import process_decisions
from root.digital_twin import FibreDigitalTwin
from root.llm_agent import get_llm_diagnosis


class OpticalHealingSimulator:
    """
    Autonomous Predictive Fault Healing Simulator for optical fibre networks.

    Pipeline per cycle:
      1. Telemetry row retrieved from pre-processed dataset
      2. Fault injected into digital twin (if event is FIBER_CUT or DEGRADING)
      3. Decision engine action applied to the twin
      4. Rule-based diagnosis produced
      5. Cycle state logged

    After all cycles, logs are exported to logs/simulation_history.csv.
    """

    def __init__(
        self,
        cycles: int = 25,
        delay: float = 0.8,
        city: str = "Lagos",
        season: str = None,
    ):
        """
        Args:
            cycles: Number of simulation steps to run.
            delay:  Seconds to pause between cycles (for readability).
            city:   Nigerian city context ('Lagos', 'Abuja', 'PortHarcourt', 'Kano').
            season: Environmental season. Defaults to current calendar season.
        """
        self.cycles = cycles
        self.delay = delay
        self.city = city
        self.season = season or get_current_season()
        self.digital_twin = FibreDigitalTwin(num_spans=15)
        self.history = []

    def run(self):
        print(f"Starting SWIFT FHS Simulation | City: {self.city} | Season: {self.season}\n")

        # Build dataset once before the simulation loop
        df = generate_network_data(n=200, city=self.city, season=self.season)
        df = simulate_ncc_drift(df, city=self.city)
        df = detect_anomalies(df, retrain=False)
        df = process_decisions(df)

        total = min(self.cycles, len(df))

        for step in range(total):
            print(f"\n{'=' * 40}")
            print(f"  Cycle {step + 1}/{total}")
            print(f"{'=' * 40}")

            row = df.iloc[step].to_dict()

            # 1. Digital Twin — inject fault when the event warrants it
            event = row.get("event", "NORMAL")
            if event in ("FIBER_CUT", "DEGRADING"):
                fault_type = "cut" if event == "FIBER_CUT" else "degradation"
                self.digital_twin.inject_fault(span_id=10, fault_type=fault_type)

            # 2. Healing action
            action = row.get("recommended_action", "NO_ACTION")
            if action != "NO_ACTION":
                self.digital_twin.apply_healing(action, span_id=10)

            # 3. Diagnosis
            diagnosis_result = get_llm_diagnosis(row)
            print("Diagnosis    :", diagnosis_result["diagnosis"])
            print("Recommendation:", diagnosis_result["suggestion"])

            # 4. Log
            self._log_state(step, row, action, diagnosis_result["diagnosis"])

            time.sleep(self.delay)

        print("\nSimulation Completed Successfully!")
        self.export_logs()

    def _log_state(self, step: int, row: dict, action: str, diagnosis: str):
        self.history.append({
            "step": step,
            "time": int(row["time"]),
            "event": row.get("event", "NORMAL"),
            "osnr_db": float(row["osnr_db"]),
            "ber": float(row["ber"]),
            "state": row.get("state", "NORMAL"),
            "action": action,
            "diagnosis": diagnosis,
        })

    def export_logs(self):
        os.makedirs("logs", exist_ok=True)
        out_path = os.path.join("logs", "simulation_history.csv")
        pd.DataFrame(self.history).to_csv(out_path, index=False)
        print(f"Logs exported -> {out_path}")