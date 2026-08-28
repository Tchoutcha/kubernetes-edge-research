"""
mark_run.py — marque le debut/fin d'un run sans toucher au script de bench.

Usage (dans un terminal a cote, pendant que antela_logger_v2.py tourne) :
    python3 mark_run.py local_10ms_rep1      # juste avant de lancer le run
    ... tu lances ton run normalement ...
    python3 mark_run.py idle                 # juste apres la fin du run

Ecrit le label + timestamp dans /tmp/current_run.txt (lu par le logger)
et garde un historique complet dans run_markers.log (utile si jamais
tu oublies de repasser a "idle" - tu pourras reconstruire apres coup).
"""
import sys
from datetime import datetime

LABEL_FILE = "/tmp/current_run.txt"
HISTORY_FILE = "run_markers.log"

if len(sys.argv) != 2:
    print("Usage: python3 mark_run.py <label>")
    print('Exemples: python3 mark_run.py local_10ms_rep1')
    print('          python3 mark_run.py idle')
    sys.exit(1)

label = sys.argv[1]
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with open(LABEL_FILE, "w") as f:
    f.write(label)

with open(HISTORY_FILE, "a") as f:
    f.write(f"{now}\t{label}\n")

print(f"[{now}] label -> {label}")
