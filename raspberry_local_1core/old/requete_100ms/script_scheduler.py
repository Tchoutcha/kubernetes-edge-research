#!/usr/bin/env python3
import re
import csv

# Nom du fichier log en entrée
log_file = "scheduler_20260416_124638.log"

# Nom du fichier CSV en sortie
csv_file = "scheduler_times.csv"

# Liste pour stocker les résultats
results = []

# Regex pour capturer duration et pod
# Exemple ligne:
# "scheduling algorithm completed" duration ="674.981µs" pod="default/helloworld7-00001-deployment-7cbfcdb89d-fhp2h"
line_regex = re.compile(r'scheduling algorithm completed".*duration\s*=\s*"([\d\.]+)(µs|ms|s)".*pod="([^"]+)"')

with open(log_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        match = line_regex.search(line)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            pod_name = match.group(3)

            # Convertir en ms
            if unit == "s":
                value_ms = value * 1000
            elif unit == "µs":
                value_ms = value / 1000
            else:  # ms
                value_ms = value

            # Extraire timestamp du début de ligne (optionnel)
            timestamp = line.split()[0] + " " + line.split()[1]

            results.append([timestamp, pod_name, value_ms])

# Écrire dans CSV
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "pod", "scheduling_time_ms"])
    writer.writerows(results)

print(f"✅ Extraction terminée ! {len(results)} lignes enregistrées dans {csv_file}")
