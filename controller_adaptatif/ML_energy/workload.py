import random
import pandas as pd

# ─────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────

# 10 ms entre requêtes = 0.01 secondes
REQUEST_INTERVAL = 10   # seconds (10 ms)

TEST_DURATION    = 20000     # seconds total

FUNCTIONS = [
    "mobilenet",
    "resnet"
]

PAYLOAD_SIZES = [
    "small",
    "medium",
    "large"
]

OUTPUT_FILE = "fixed_workload.csv"

# ─────────────────────────────────────────────────────
# FIXED SEED (reproductible)
# ─────────────────────────────────────────────────────
random.seed(42)

# ─────────────────────────────────────────────────────
# GENERATION DU WORKLOAD
# ─────────────────────────────────────────────────────
workload = []

t = 0.0
request_id = 0

while t < TEST_DURATION:

    fn   = random.choice(FUNCTIONS)
    size = random.choice(PAYLOAD_SIZES)

    workload.append({
        "request_id": request_id,
        "scheduled_time": round(t, 3),
        "function": fn,
        "payload_size": size,
    })

    request_id += 1
    t += REQUEST_INTERVAL

# ─────────────────────────────────────────────────────
# SAVE CSV
# ─────────────────────────────────────────────────────
df = pd.DataFrame(workload)
df.to_csv(OUTPUT_FILE, index=False)

# ─────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────
print("=" * 60)
print("FIXED WORKLOAD GENERATED")
print("=" * 60)

print(f"Saved file      : {OUTPUT_FILE}")
print(f"Total requests  : {len(df)}")
print(f"Duration        : {TEST_DURATION}s")
print(f"Request interval: {REQUEST_INTERVAL}s (10 ms)")
print(f"Rate             : {1/REQUEST_INTERVAL:.2f} req/s")

print("\nFunction distribution:")
print(df["function"].value_counts())

print("\nPayload distribution:")
print(df["payload_size"].value_counts())

print("\nFirst requests:")
print(df.head())
