#!/usr/bin/env python3

"""
Enoslib script to:
1. Reserve a node on Grid5000 (parasilo cluster, rennes site)
2. Install K3s
3. Install Knative Serving + Kourier
4. Configure DNS
5. Create Docker Hub secret
6. Upload profiling data and script
7. Run the profiling script
8. Retrieve results
"""

import logging
import time
from pathlib import Path

import enoslib as en

# ============================================
# CONFIGURATION
# ============================================
CLUSTER        = "parasilo"
SITE           = "rennes"
WALLTIME       = "4:00:00"        # adjust based on expected profiling duration
JOB_NAME       = "knative-profiling"

KNATIVE_VERSION = "v1.21.0"
DOCKERHUB_USERNAME = "arjiba"
DOCKERHUB_PASSWORD = "elma2017?"   # replace with your password
DOCKERHUB_EMAIL    = "ahmed.rjiba@inria.fr"    # replace with your email
DOCKERHUB_SECRET   = "dockerhub-secret"

NODE_IP_PLACEHOLDER = ""   # will be set dynamically after reservation

LOCAL_DATA_DIR    = "./Profiling/"           # local path to payload data
LOCAL_SCRIPT      = "./knative_profile_all.sh"   # local profiling script
REMOTE_BASE_DIR   = "/tmp/Profiling"            # remote working directory
REMOTE_RESULTS    = f"{REMOTE_BASE_DIR}/results" # where CSVs will be saved
LOCAL_RESULTS_DIR = "./results"                  # where to download CSVs

# ============================================
# SETUP LOGGING
# ============================================
en.init_logging(level=logging.INFO)
en.check()

# ============================================
# STEP 1 — RESERVE NODE
# ============================================
print("\n============================================")
print(" STEP 1: Reserving node on Grid5000")
print("============================================")

conf = (
    en.G5kConf.from_settings(
        job_name=JOB_NAME,
        walltime=WALLTIME,
    )
    .add_machine(
        roles=["knative"],
        cluster=CLUSTER,
        nodes=1,
    )
)

provider = en.G5k(conf)
roles, networks = provider.init()
en.wait_for(roles)

# Get the node host object
node = roles["knative"][0]
node_address = node.address
print(f"✅ Node reserved: {node_address}")

# ============================================
# STEP 2 — INSTALL DEPENDENCIES
# ============================================
print("\n============================================")
print(" STEP 2: Installing dependencies")
print("============================================")

with en.actions(roles=roles["knative"]) as a:
    a.apt(
        name=["curl", "wget", "jq", "bc", "apt-transport-https", "ca-certificates"],
        state="present",
        update_cache=True,
    )

print("✅ Dependencies installed")

# ============================================
# STEP 3 — INSTALL K3S
# ============================================
print("\n============================================")
print(" STEP 3: Installing K3s")
print("============================================")

en.run_command(
    "curl -sfL https://get.k3s.io | sh -s - --disable traefik --write-kubeconfig-mode 644",
    roles=roles["knative"],
)

# Wait for K3s to be ready
time.sleep(15)

en.run_command(
    "kubectl wait --for=condition=Ready nodes --all --timeout=120s",
    roles=roles["knative"],
    extra_vars={"KUBECONFIG": "/etc/rancher/k3s/k3s.yaml"},
)

print("✅ K3s installed")

# ============================================
# STEP 4 — INSTALL KNATIVE SERVING
# ============================================
print("\n============================================")
print(" STEP 4: Installing Knative Serving")
print("============================================")

knative_cmds = [
    f"kubectl apply -f https://github.com/knative/serving/releases/download/knative-{KNATIVE_VERSION}/serving-crds.yaml",
    f"kubectl apply -f https://github.com/knative/serving/releases/download/knative-{KNATIVE_VERSION}/serving-core.yaml",
    "kubectl wait --for=condition=Ready pods --all -n knative-serving --timeout=180s",
]

for cmd in knative_cmds:
    en.run_command(
        cmd,
        roles=roles["knative"],
        extra_vars={"KUBECONFIG": "/etc/rancher/k3s/k3s.yaml"},
    )

print("✅ Knative Serving installed")

# ============================================
# STEP 5 — INSTALL KOURIER
# ============================================
print("\n============================================")
print(" STEP 5: Installing Kourier")
print("============================================")

kourier_cmds = [
    f"kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-{KNATIVE_VERSION}/kourier.yaml",
    """kubectl patch configmap/config-network \
        --namespace knative-serving \
        --type merge \
        --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'""",
    "kubectl wait --for=condition=Ready pods --all -n kourier-system --timeout=180s",
]

for cmd in kourier_cmds:
    en.run_command(
        cmd,
        roles=roles["knative"],
        extra_vars={"KUBECONFIG": "/etc/rancher/k3s/k3s.yaml"},
    )

print("✅ Kourier installed")

# ============================================
# STEP 6 — CONFIGURE DNS
# ============================================
print("\n============================================")
print(" STEP 6: Configuring DNS")
print("============================================")

# Get node IP dynamically
result = en.run_command(
    "kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}'",
    roles=roles["knative"],
    extra_vars={"KUBECONFIG": "/etc/rancher/k3s/k3s.yaml"},
)
node_ip = result[0].payload["stdout"].strip()
print(f"Node IP: {node_ip}")

en.run_command(
    f"""kubectl patch configmap config-domain \
        --namespace knative-serving \
        --type merge \
        --patch '{{"data":{{"{node_ip}.sslip.io":""}}}}'""",
    roles=roles["knative"],
    extra_vars={"KUBECONFIG": "/etc/rancher/k3s/k3s.yaml"},
)

print(f"✅ DNS configured: {node_ip}.sslip.io")

# ============================================
# STEP 7 — Update Configmap config-autoscaler
# ============================================
print("\n============================================")
print(" STEP 7 — Update Configmap")
print("============================================")

en.run_command(
    """kubectl patch configmap config-autoscaler -n knative-serving --type merge -p '{"data":{"allow-zero-initial-scale":"true","stable-window":"10s", "scale-to-zero-grace-period":"0s"}}'""",
    roles=roles["knative"],
)

print(f"✅ Config-autoscaler updated")


# ============================================
# STEP 8 — Docker Install
# ============================================
print("\n============================================")
print(" STEP 8 — Docker Install")
print("============================================")

en.run_command(
    "g5k-setup-docker -t",
    roles=roles["knative"],
)

print(f"✅ Docker Installed")


# ============================================
# STEP 7 — CREATE DOCKER HUB SECRET
# ============================================
print("\n============================================")
print(" STEP 7: Creating Docker Hub secret")
print("============================================")

en.run_command(
    f"""kubectl create secret docker-registry {DOCKERHUB_SECRET} \
        --docker-username={DOCKERHUB_USERNAME} \
        --docker-password={DOCKERHUB_PASSWORD} \
        --docker-email={DOCKERHUB_EMAIL} \
        --namespace=default \
        --dry-run=client -o yaml | kubectl apply -f -""",
    roles=roles["knative"],
    extra_vars={"KUBECONFIG": "/etc/rancher/k3s/k3s.yaml"},
)

print("✅ Docker Hub secret created")

# ============================================
# STEP 8 — UPLOAD DATA AND SCRIPTS
# ============================================
print("\n============================================")
print(" STEP 8: Uploading data and profiling script")
print("============================================")

# Create remote directories
en.run_command(
    f"mkdir -p {REMOTE_BASE_DIR}/data {REMOTE_RESULTS}",
    roles=roles["knative"],
)

# Upload files using enoslib copy
with en.actions(roles=roles["knative"]) as a:
    # Upload profiling script
    a.copy(
        src=LOCAL_SCRIPT,
        dest=f"{REMOTE_BASE_DIR}/knative_profile_all.sh",
    )
    # Upload payload data directory
    a.copy(
        src=f"{LOCAL_DATA_DIR}/",
        dest=f"{REMOTE_BASE_DIR}/data/",
    )

print("✅ Data and scripts uploaded")

# ============================================
# STEP 9 — RUN PROFILING SCRIPT
# ============================================
print("\n============================================")
print(" STEP 9: Running profiling script")
print("============================================")

en.run_command(
    f"cd {REMOTE_BASE_DIR} && KUBECONFIG=/etc/rancher/k3s/k3s.yaml nohup bash knative_profile_all.sh > {REMOTE_BASE_DIR}/profiling.log 2>&1",
    roles=roles["knative"],
)

print("✅ Profiling complete")

# ============================================
# STEP 10 — RETRIEVE RESULTS
# ============================================
print("\n============================================")
print(" STEP 10: Downloading results")
print("============================================")

Path(LOCAL_RESULTS_DIR).mkdir(parents=True, exist_ok=True)

# Archive results into a single tar file on the remote node
en.run_command(
    f"tar -czf {REMOTE_BASE_DIR}/results.tar.gz -C {REMOTE_BASE_DIR} results profiling.log",
    roles=roles["knative"],
)

# Fetch the tar file and the log
with en.actions(roles=roles["knative"]) as a:
    a.fetch(
        src=f"{REMOTE_BASE_DIR}/results.tar.gz",
        dest=f"{LOCAL_RESULTS_DIR}/results.tar.gz",
        flat=True,
    )

# Extract locally
import subprocess
subprocess.run(
    ["tar", "-xzf", f"{LOCAL_RESULTS_DIR}/results.tar.gz", "-C", LOCAL_RESULTS_DIR],
    check=True,
)

print(f"✅ Results downloaded to {LOCAL_RESULTS_DIR}")

# ============================================
# SUMMARY
# ============================================
print("\n============================================")
print(" PROFILING COMPLETE")
print("============================================")
print(f"Node          : {node_address}")
print(f"Node IP       : {node_ip}")
print(f"Results saved : {LOCAL_RESULTS_DIR}")
print("")

# List downloaded files
result_files = list(Path(LOCAL_RESULTS_DIR).glob("*.csv"))
print(f"CSV files ({len(result_files)}):")
for f in result_files:
    print(f"  - {f}")

# ============================================
# CLEANUP — uncomment to release node after profiling
# ============================================
# print("\nReleasing Grid5000 resources...")
# provider.destroy()
# print("✅ Resources released")