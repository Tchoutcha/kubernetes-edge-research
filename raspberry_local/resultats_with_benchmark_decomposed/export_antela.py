import requests
import csv
import time
from datetime import datetime

HA_URL = "http://127.0.0.1:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIxNmQ0ZGM3NzJkZDM0MTY5ODhiZWFkNGIwMGJiZjQyNSIsImlhdCI6MTc4MTE3NTA3MiwiZXhwIjoyMDk2NTM1MDcyfQ.-UD3L7zj6vIpFP70Uwjp6q0emwS2EDQQsGEm4KBmSKY"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}

SENSORS = {
    "power": "sensor.bandeau_d_alimentation_antela_puissance",
    "voltage": "sensor.bandeau_d_alimentation_antela_tension",
    "current": "sensor.bandeau_d_alimentation_antela_courant",
    "energy": "sensor.bandeau_d_alimentation_antela_energie_totale"
}

CSV_FILE = "antela_data.csv"

# header CSV
with open(CSV_FILE, "a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Time", "Power_W", "Voltage_V", "Current_A", "Energy_kWh"])

while True:
    values = {}

    for key, entity in SENSORS.items():
        try:
            r = requests.get(
                f"{HA_URL}/api/states/{entity}",
                headers=HEADERS,
                timeout=5
            )

            data = r.json()
            values[key] = data.get("state", "0")

        except Exception as e:
            print("Erreur:", e)
            values[key] = "0"

    now = datetime.now()

    print(values)

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            values["power"],
            values["voltage"],
            values["current"],
            values["energy"]
        ])

    time.sleep(1)
