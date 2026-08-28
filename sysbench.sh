#!/bin/bash

# =============================================================================
# Script de benchmark sysbench avec intervalles et pauses configurables
# Intervalles : 2ms, 10ms, 50ms, 100ms, 200ms, 1s
# Répétitions : 10 fois par intervalle
# Pause entre chaque série : 1 heure
# =============================================================================

RESULT_DIR="./sysbench_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$RESULT_DIR/benchmark_global_$TIMESTAMP.log"

mkdir -p "$RESULT_DIR"

# -----------------------------------------------------------------------------
# Fonction : afficher et logger un message
# -----------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# -----------------------------------------------------------------------------
# Fonction : lancer sysbench N fois avec un intervalle donné
#   $1 = intervalle en millisecondes (ex: 2, 10, 50...)
#   $2 = nombre de répétitions
#   $3 = fichier de sortie
# -----------------------------------------------------------------------------
run_series() {
    local interval_ms=$1
    local repetitions=$2
    local output_file=$3

    log "========================================================"
    log "Début de la série  : intervalle = ${interval_ms}ms, répétitions = ${repetitions}"
    log "Fichier de résultat : $output_file"
    log "========================================================"

    # En-tête du fichier de résultats
    {
        echo "# Benchmark sysbench — intervalle : ${interval_ms}ms"
        echo "# Date de début : $(date '+%Y-%m-%d %H:%M:%S')"
        echo "# ======================================================"
    } > "$output_file"

    for ((i = 1; i <= repetitions; i++)); do
        log "  → Exécution $i/$repetitions (intervalle ${interval_ms}ms)..."

        {
            echo ""
            echo "--- Exécution n°$i — $(date '+%Y-%m-%d %H:%M:%S') ---"
        } >> "$output_file"

        # ------------------------------------------------------------------
        # Commande sysbench — adaptez les paramètres à votre besoin :
        #   - cpu   : test CPU
        #   - --time=0 + --events=1 pour une seule mesure rapide
        #   Remplacez cette ligne par votre propre commande sysbench
        # ------------------------------------------------------------------
        sysbench cpu \
            --cpu-max-prime=2000 \
            --threads=1 \
            --time=0 \
            --events=1 \
            run >> "$output_file" 2>&1

        log "     Exécution $i terminée."

        # Pause entre chaque lancement (sauf après le dernier)
        if (( i < repetitions )); then
            log "     Attente de ${interval_ms}ms avant le prochain lancement..."
            # Convertit ms en secondes pour sleep (utilise bc pour les décimales)
            sleep_sec=$(echo "scale=6; $interval_ms / 1000" | bc)
            sleep "$sleep_sec"
        fi
    done

    {
        echo ""
        echo "# ======================================================"
        echo "# Date de fin : $(date '+%Y-%m-%d %H:%M:%S')"
    } >> "$output_file"

    log "Série ${interval_ms}ms terminée. Résultats dans : $output_file"
}

# -----------------------------------------------------------------------------
# Fonction : pause d'une heure avec compte à rebours
# -----------------------------------------------------------------------------
wait_one_hour() {
    local total=3600
    log "Début de la pause d'1 heure..."
    for ((remaining = total; remaining > 0; remaining -= 60)); do
        log "  Pause en cours — encore ${remaining}s (~$(( remaining / 60 )) min)"
        sleep 60
    done
    log "Pause terminée. Reprise du benchmark."
}

# =============================================================================
# PROGRAMME PRINCIPAL
# =============================================================================

log "Démarrage du benchmark global"
log "Répertoire de résultats : $RESULT_DIR"

# ---- Série 1 : toutes les 2 ms ----
run_series 2 10 "$RESULT_DIR/resultats_2ms_$TIMESTAMP.txt"
wait_one_hour

# ---- Série 2 : toutes les 10 ms ----
run_series 10 10 "$RESULT_DIR/resultats_10ms_$TIMESTAMP.txt"
wait_one_hour

# ---- Série 3 : toutes les 50 ms ----
run_series 50 10 "$RESULT_DIR/resultats_50ms_$TIMESTAMP.txt"
wait_one_hour

# ---- Série 4 : toutes les 100 ms ----
run_series 100 10 "$RESULT_DIR/resultats_100ms_$TIMESTAMP.txt"
wait_one_hour

# ---- Série 5 : toutes les 200 ms ----
run_series 200 10 "$RESULT_DIR/resultats_200ms_$TIMESTAMP.txt"
wait_one_hour

# ---- Série 6 : toutes les 1 s ----
run_series 1000 10 "$RESULT_DIR/resultats_1000ms_$TIMESTAMP.txt"

log "========================================================"
log "Benchmark global terminé."
log "Tous les résultats sont dans : $RESULT_DIR/"
log "========================================================"
