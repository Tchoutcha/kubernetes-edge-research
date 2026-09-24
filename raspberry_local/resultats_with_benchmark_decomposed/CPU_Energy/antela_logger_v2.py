import requests
import csv
import time
import os
from datetime import datetime

HA_URL = "http://127.0.0.1:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIxNmQ0ZGM3NzJkZDM0MTY5ODhiZWFkNGIwMGJiZjQyNSIsImlhdCI6MTc4MTE3NTA3MiwiZXhwIjoyMDk2NTM1MDcyfQ.-UD3L7zj6vIpFP70Uwjp6q0emwS2EDQQsGEm4KBmSKY"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

SENSORS = {
    "power": "sensor.bandeau_d_alimentation_antela_puissance",
    "voltage": "sensor.bandeau_d_alimentation_antela_tension",
    "current": "sensor.bandeau_d_alimentation_antela_courant",
    "energy": "sensor.bandeau_d_alimentation_antela_energie_totale",  # garde-la : integree par le capteur, plus precise que notre propre integration
}

# --- NOUVEAU : un fichier par session, nomme avec la date/heure de lancement ---
# Fini le fichier unique qui grossit indefiniment et qu'on doit recouper a la main plus tard.
session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILE = f"antela_data_{session_ts}.csv"

# --- NOUVEAU : fichier de marqueur partage avec le script de bench ---
# Le script qui envoie les requetes doit ecrire dedans, ex:
#   with open("/tmp/current_run.txt", "w") as f:
#       f.write("local_10ms_rep3")
# et remettre "idle" une fois le run termine.
LABEL_FILE = "/tmp/current_run.txt"


def read_label():
    try:
        with open(LABEL_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"


with open(CSV_FILE, "a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Time", "Power_W", "Voltage_V", "Current_A", "Energy_kWh", "Label"])

print(f"Logging vers {CSV_FILE}")

while True:
    values = {}
    for key, entity in SENSORS.items():
        try:
            r = requests.get(f"{HA_URL}/api/states/{entity}", headers=HEADERS, timeout=5)
            data = r.json()
            values[key] = data.get("state", "0")
        except Exception as e:
            print("Erreur:", e)
            values[key] = "0"

    label = read_label()
    now = datetime.now()
    print(values, label)

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            values["power"],
            values["voltage"],
            values["current"],
            values["energy"],
            label,
        ])
    time.sleep(1)
