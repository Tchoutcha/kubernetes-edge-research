#!/usr/bin/env python3
import json
import csv
import re

# Nom du fichier log en entrée
log_file = "activator_20260423_122510.log"

# Nom du fichier CSV en sortie
csv_file = "context_handler_times7.csv"

# Liste pour stocker les résultats
results = []

# Regex pour extraire le temps avec l'unité (ex: 4.742600295s, 123.45ms, 678µs)
time_regex = re.compile(r"Throttler Try took:\s*([\d\.]+)(ms|µs|s)")

with open(log_file, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            message = data.get("message", "")
            match = time_regex.search(message)
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                # Convertir en ms
                if unit == "s":
                    value_ms = value * 1000
                elif unit == "µs":
                    value_ms = value / 1000
                else:  # déjà en ms
                    value_ms = value
                timestamp = data.get("timestamp", "")
                pod_name = data.get("knative.dev/pod", "")
                results.append([timestamp, pod_name, value_ms])
        except json.JSONDecodeError:
            continue

# Écrire les résultats dans un CSV
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "pod", "context_handler_time_ms"])
    writer.writerows(results)

print(f"✅ Extraction terminée ! {len(results)} lignes enregistrées dans {csv_file}")
