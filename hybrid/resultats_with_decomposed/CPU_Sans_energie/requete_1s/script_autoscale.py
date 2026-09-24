#!/usr/bin/env python3
import json
import csv

# Nom du fichier log en entrée
log_file = "autoscaler_20260604_111737.log"

# Nom du fichier CSV en sortie
csv_file = "reconcile_times2.csv"

# Liste pour stocker les résultats
results = []

with open(log_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            message = data.get("message", "")
            if message == "Reconcile succeeded":
                duration_str = data.get("duration", "").strip()

                # Vérifier et convertir selon l'unité
                if duration_str.endswith("ms"):
                    value_ms = float(duration_str.replace("ms", ""))
                elif duration_str.endswith("s"):
                    value_ms = float(duration_str.replace("s", "")) * 1000
                elif "µs" in duration_str or "µ" in duration_str:
                    # gère µs ou µ mal encodé
                    value_ms = float(duration_str.replace("µs", "").replace("µ", "")) / 1000
                else:
                    # unité inconnue, ignorer
                    continue

                timestamp = data.get("timestamp", "")
                podautoscaler = data.get("knative.dev/key", "")
                results.append([timestamp, podautoscaler, value_ms])
        except json.JSONDecodeError:
            continue
        except ValueError:
            # ignorer les valeurs non convertibles
            continue

# Écrire les résultats dans un CSV
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "podautoscaler", "reconcile_time_ms"])
    writer.writerows(results)

print(f"✅ Extraction terminée ! {len(results)} lignes enregistrées dans {csv_file}")
