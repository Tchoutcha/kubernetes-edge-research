"""
Annual cost savings vs Local baseline.
Layout: 3 rows (regions) x 5 columns (delays) — one single figure.

Usage:
    python3 energy_cost_savings.py --servers 1000000
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import argparse
import os

plt.rcParams.update({
    "font.family":       "serif",
    "font.serif":        ["Times New Roman", "DejaVu Serif"],
    "font.size":         11,
    "axes.titlesize":    11,
    "axes.labelsize":    10,
    "xtick.labelsize":   9,
    "ytick.labelsize":   9,
    "legend.fontsize":   10,
    "axes.linewidth":    0.8,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "pdf.fonttype":      42,
    "ps.fonttype":       42,
})

REGIONS = {
    'virginia':  {'name': 'N. Virginia', 'price_per_kwh': 0.1085, 'currency': '$'},
    'ireland':   {'name': 'Ireland',     'price_per_kwh': 0.1374, 'currency': '€'},
    'singapore': {'name': 'Singapore',   'price_per_kwh': 0.2184, 'currency': 'S$'},
}

HOURS_PER_YEAR = 8760

STYLES = {
    "Hybrid":           {"color": "#0072B2", "hatch": "//"},
    "Local 1core":      {"color": "#009E73", "hatch": "xx"},
    "Local Apiserver":  {"color": "#CC0000", "hatch": "\\\\"},
}
BASELINE       = "Local"
BASELINE_COLOR = "#D55E00"
ARCHS          = list(STYLES.keys())
DELAYS         = ["10ms", "50ms", "100ms", "200ms", "1s"]
DATA_DIR       = "."

FILES = {
    "Local":           {d: f"power_{d}.csv"           for d in DELAYS},
    "Local 1core":     {d: f"power_{d}_1core.csv"     for d in DELAYS},
    "Hybrid":          {d: f"power_{d}_hybrid.csv"    for d in DELAYS},
    "Local Apiserver": {d: f"power_{d}_apiserver.csv" for d in DELAYS},
}
POWER_COL = "Power_W"

def compute_max(filepath):
    if not os.path.exists(filepath):
        return np.nan
    try:
        df = pd.read_csv(filepath)
        s  = pd.to_numeric(df[POWER_COL], errors='coerce').dropna()
        return float(s.max()) if len(s) > 0 else np.nan
    except Exception:
        return np.nan

def annual_cost(power_w, price, n):
    return (power_w / 1000) * HOURS_PER_YEAR * price * n

def saving(p_base, p_cfg, price, n):
    return annual_cost(p_base, price, n) - annual_cost(p_cfg, price, n)

# ── Args ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--servers', type=int, default=1_000_000)
args      = parser.parse_args()
N_SERVERS = args.servers
print(f"\n=== {N_SERVERS:,} servers ===\n")

# ── Load power ────────────────────────────────────────────────────────────────
all_archs = [BASELINE] + ARCHS
power = {arch: {} for arch in all_archs}
for arch in all_archs:
    for delay in DELAYS:
        power[arch][delay] = compute_max(
            os.path.join(DATA_DIR, FILES[arch][delay]))

# ── Figure : 3 rows x 5 cols ──────────────────────────────────────────────────
n_rows = len(REGIONS)
n_cols = len(DELAYS)
fig, axes = plt.subplots(n_rows, n_cols,
                         figsize=(4.2 * n_cols, 4.0 * n_rows),
                         sharey='row')

region_list = list(REGIONS.items())

for ri, (region_key, region) in enumerate(region_list):
    for ci, delay in enumerate(DELAYS):
        ax = axes[ri][ci]

        p_base = power[BASELINE][delay]

        for i, arch in enumerate(ARCHS):
            p   = power[arch][delay]
            val = np.nan if (np.isnan(p) or np.isnan(p_base)) \
                  else saving(p_base, p, region['price_per_kwh'], N_SERVERS) / 1e6

            if np.isnan(val):
                continue

            ax.bar(
                i, val,
                width=0.5,
                color=STYLES[arch]["color"],
                hatch=STYLES[arch]["hatch"],
                edgecolor="white",
                linewidth=0.6,
                alpha=0.88,
                zorder=3,
            )
            # Annotation value only — no extra label
            va   = "bottom" if val >= 0 else "top"
            yoff = abs(val) * 0.03
            ax.text(
                i,
                val + yoff if val >= 0 else val - yoff,
                f"{val:+.1f}M",
                ha="center", va=va,
                fontsize=8, color=STYLES[arch]["color"],
                fontweight="bold",
            )

        ax.axhline(0, color="black", linewidth=0.7)

        # Baseline cost — simple text bottom left
        if not np.isnan(p_base):
            bc = annual_cost(p_base, region['price_per_kwh'], N_SERVERS) / 1e6
            ax.text(
                0.02, 0.02,
                f"Local: {region['currency']}{bc:.1f}M",
                transform=ax.transAxes,
                ha="left", va="bottom",
                fontsize=7.5, color=BASELINE_COLOR,
                fontstyle="italic",
            )

        # Column title (delay) — only top row
        if ri == 0:
            ax.set_title(delay, fontweight="bold", fontsize=11, pad=6)

        # Row label (region) — only left column
        if ci == 0:
            ax.set_ylabel(
                f"{region['name']}\nSavings vs Local (M{region['currency']})",
                fontsize=9)

        ax.set_xticks(range(len(ARCHS)))
        ax.set_xticklabels(ARCHS, fontsize=8, rotation=12, ha="right")
        ax.grid(True, axis="y", linestyle=":", linewidth=0.35, color="0.80", zorder=0)
        ax.grid(False, axis="x")
        ax.tick_params(axis="both", direction="out", length=3, width=0.6)

# ── Shared legend ─────────────────────────────────────────────────────────────
handles = [
    mpatches.Patch(facecolor=STYLES[a]["color"], hatch=STYLES[a]["hatch"],
                   edgecolor="white", alpha=0.88, label=a)
    for a in ARCHS
]
handles.append(
    mpatches.Patch(facecolor=BASELINE_COLOR, alpha=0.88, label=BASELINE + " (baseline)")
)
fig.legend(handles=handles, loc="lower center", ncol=len(ARCHS)+1,
           bbox_to_anchor=(0.5, -0.03), fontsize=10,
           framealpha=0.95, edgecolor="0.80")

fig.suptitle(
    f"Annual Cost Savings vs Local Baseline  —  {N_SERVERS:,} servers  ·  8760 h/year  ·  Peak power\n"
    f"Positive = cheaper than Local   |   Negative = more expensive than Local",
    fontsize=12, fontweight="bold", y=1.01
)

plt.tight_layout(rect=[0, 0.04, 1, 1])
fname = f"fig_savings_grid_{N_SERVERS//1000}K"
fig.savefig(f"{fname}.pdf", dpi=300, bbox_inches="tight")
fig.savefig(f"{fname}.png", dpi=300, bbox_inches="tight")
print(f"✓ Saved: {fname}.pdf / .png")
