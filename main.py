from simulator import OpticalHealingSimulator

if __name__ == "__main__":
    simulator = OpticalHealingSimulator(
        cycles=30,          # Number of simulation steps
        delay=0.8,          # Delay between steps (seconds)
        city="Lagos",       # Nigerian city context
        season=None,        # None = auto-detect from current calendar month
    )
    simulator.run()