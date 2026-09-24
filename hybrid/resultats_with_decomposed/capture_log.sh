#!/bin/bash

# ---------------- Paramètres ----------------

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ACTIVATOR_LOG="activator_$TIMESTAMP.log"
AUTOSCALER_LOG="autoscaler_$TIMESTAMP.log"
SCHEDULER_LOG="scheduler_$TIMESTAMP.log"


echo "Starting log capture..."
echo "Activator logs -> $ACTIVATOR_LOG"
echo "Autoscaler logs -> $AUTOSCALER_LOG"
echo "Scheduler logs -> $SCHEDULER_LOG"
echo "container logs -> LOG"
# ---------------- Démarrer la capture ----------------

kubectl logs -f -n knative-serving deploy/activator >> "$ACTIVATOR_LOG" 2>&1 &
kubectl logs -f -n knative-serving deploy/autoscaler >> "$AUTOSCALER_LOG" 2>&1 &
kubectl logs -f -n kube-system my-scheduler-668bffc96f-89m7t >> "$SCHEDULER_LOG" 2>&1 &
kubectl logs -f -n kourier-system 3scale-kourier-gateway-6578f5c6f9-bz9pf > kourier.txt



echo "Logs are now streaming in background..."
echo "Use 'jobs' or 'ps' to check background processes."
echo "Ctrl+C won't stop background jobs, use 'kill %job_number' to terminate."
