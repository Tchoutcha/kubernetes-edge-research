

from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Style global
# ---------------------------------------------------------------------------

plt.rcParams["font.family"] = "Liberation Serif"
plt.rcParams["font.size"] = 12
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False


# ---------------------------------------------------------------------------
# Couleurs, hachures et labels
# ---------------------------------------------------------------------------

WONG = {
    "local": "0.75",
    "1core": "0.55",
    "apiserver": "0.35",
    "adaptive": "white",
}

HATCHES = {
    "local": None,
    "1core": None,
    "apiserver": None,
    "adaptive": "//",
}

LABELS = {
    "local": "Local",
    "1core": "Local 1core",
    "apiserver": "Local Apiserver",
    "adaptive": "Adaptive (ACPC)",
}


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

class Args:
    try:
        script_dir = Path(__file__).resolve().parent
    except NameError:
        # Compatible Jupyter
        script_dir = Path.cwd()

    csv_path = script_dir / "CPU_all_configs_with2s10s_FINAL.csv"
    out_dir = script_dir / "figures_CPU_v2"

    delay_order = ["10ms", "50ms", "100ms", "200ms", "1s", "2s", "10s"]
    config_order = ["local", "1core", "apiserver", "adaptive"]


# ---------------------------------------------------------------------------
# Graphe en barres groupées
# ---------------------------------------------------------------------------

def grouped_bar(
    df,
    value_col,
    ylabel,
    title,
    out_prefix,
    args,
):
    fig, ax = plt.subplots(figsize=(9, 5.5))

    n_configs = len(args.config_order)
    bar_width = 0.8 / n_configs
    x = list(range(len(args.delay_order)))

    for i, cfg in enumerate(args.config_order):
        sub = (
            df[df["config"] == cfg]
            .drop_duplicates(subset=["delay"], keep="last")
            .set_index("delay")
        )

        values = [
            sub[value_col].get(delay, float("nan"))
            for delay in args.delay_order
        ]

        positions = [
            xi + i * bar_width - 0.4 + bar_width / 2
            for xi in x
        ]

        plot_pos = []
        plot_val = []

        for position, value in zip(positions, values):
            if pd.notna(value):
                plot_pos.append(position)
                plot_val.append(value)

        if not plot_val:
            print(f"Aucune donnée pour {cfg} dans {value_col}")
            continue

        # Aucune barre d'erreur :
        # aucun yerr, capsize ou error_kw.
        ax.bar(
            plot_pos,
            plot_val,
            width=bar_width,
            label=LABELS[cfg],
            color=WONG[cfg],
            hatch=HATCHES[cfg],
            edgecolor="black",
            linewidth=0.6,
            zorder=3,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(args.delay_order)

    ax.set_xlabel("Inter-request Delay")
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    ax.legend(
        frameon=False,
        fontsize=9,
        ncol=2,
    )

    ax.grid(
        axis="y",
        linestyle=":",
        linewidth=0.5,
        alpha=0.6,
        zorder=0,
    )

    ax.set_axisbelow(True)

    fig.tight_layout()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / f"{out_prefix}.pdf"
    png_path = out_dir / f"{out_prefix}.png"

    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")

    plt.close(fig)

    print(f"Sauvegarde -> {pdf_path}")
    print(f"Sauvegarde -> {png_path}")


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main(args):
    csv_path = Path(args.csv_path)

    if not csv_path.is_file():
        raise FileNotFoundError(
            f"CSV introuvable : {csv_path}\n"
            ""
            ""
        )

    df = pd.read_csv(csv_path)

    required_columns = {
        "config",
        "delay",
        "energy_total_J",
        "J_per_req_mean",
        "max_power_W",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "Colonnes manquantes dans le CSV : "
            + ", ".join(sorted(missing_columns))
        )

    df["config"] = df["config"].astype(str).str.strip()
    df["delay"] = df["delay"].astype(str).str.strip()

    grouped_bar(
        df=df,
        value_col="energy_total_J",
        ylabel="Total Energy (J)",
        title="",
        out_prefix="total_energy_per_delay_CPU",
        args=args,
    )

    grouped_bar(
        df=df,
        value_col="J_per_req_mean",
        ylabel="Energy per Invocation (J/req)",
        title="",
        out_prefix="energy_per_invocation_CPU",
        args=args,
    )

    grouped_bar(
        df=df,
        value_col="max_power_W",
        ylabel="Max Power (W)",
        title="",
        out_prefix="max_power_per_delay_CPU",
        args=args,
    )


if __name__ == "__main__":
    main(Args())
