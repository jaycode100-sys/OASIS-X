# import pandas as pd
# import numpy as np
# import sklearn
# import matplotlib.pyplot as plt

# print("Everything installed correctly!")

from models.data_simulator import generate_network_data
from models.anomaly_detector import detect_anomalies
df = generate_network_data(200)
df = detect_anomalies(df)
print(df[['time', 'osnr_db', 'event', 'anomaly_flag']].tail(10))
