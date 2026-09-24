from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Style global
# ---------------------------------------------------------------------------

plt.rcParams["font.family"] = "Liberation Serif"
plt.rcParams["font.size"] = 10

plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False


# ---------------------------------------------------------------------------
# Couleurs / hachures / labels
# ---------------------------------------------------------------------------

WONG = {
    "local": "#0072B2",
    "1core": "#009E73",
    "apiserver": "#E64B35",
    "adaptive": "#CC79A7",
}

HATCHES = {
    "local": "//",
    "1core": "xx",
    "apiserver": "\\\\",
    "adaptive": "++",
}

LABELS = {
    "local": "Local (shared)",
    "1core": "Local 1core (elevated scheduler priority)",
    "apiserver": "Local Apiserver (master reserved)",
    "adaptive": "ACP (adaptive reference)",
}


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

class Args:

    try:
        script_dir = Path(__file__).resolve().parent
    except NameError:
        script_dir = Path.cwd()

    csv_path = script_dir / "ML_all_configs_FINAL_with2s10s.csv"
    out_dir = script_dir / "figures_Ml"

    delay_order = [
        "10ms",
        "50ms",
        "100ms",
        "200ms",
        "1s",
        "2s",
        "10s"
    ]

    config_order = [
        "local",
        "1core",
        "apiserver",
        "adaptive",
    ]


# ---------------------------------------------------------------------------
# Figure : Energy per Invocation + Peak Power
# ---------------------------------------------------------------------------

def plot_energy_power(df, args):

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(10, 4.5),
        sharex=True
    )

    # -----------------------------------------------------------------------
    # Paramètres des barres
    # -----------------------------------------------------------------------

    n_configs = len(args.config_order)

    group_width = 0.80

    bar_width = group_width / n_configs

    x = list(range(len(args.delay_order)))

    # -----------------------------------------------------------------------
    # Deux métriques
    # -----------------------------------------------------------------------

    plots = [
        (
            axes[0],
            "J_per_req_mean",
            "Energy per invocation",
        ),
        (
            axes[1],
            "max_power_W",
            "Peak power",
        ),
    ]

    # -----------------------------------------------------------------------
    # Tracer chaque subplot
    # -----------------------------------------------------------------------

    for ax, value_col, title in plots:

        # -------------------------------------------------------------------
        # Récupérer les valeurs ACP
        # -------------------------------------------------------------------

        acp_sub = (
            df[df["config"] == "adaptive"]
            .drop_duplicates(
                subset=["delay"],
                keep="last"
            )
            .set_index("delay")
        )

        # -------------------------------------------------------------------
        # Tracer les configurations
        # -------------------------------------------------------------------

        for i, cfg in enumerate(args.config_order):

            sub = (
                df[df["config"] == cfg]
                .drop_duplicates(
                    subset=["delay"],
                    keep="last"
                )
                .set_index("delay")
            )

            # ---------------------------------------------------------------
            # Valeurs
            # ---------------------------------------------------------------

            values = [
                sub[value_col].get(
                    delay,
                    float("nan")
                )
                for delay in args.delay_order
            ]

            # ---------------------------------------------------------------
            # Positions
            # ---------------------------------------------------------------

            positions = [
                xi
                + i * bar_width
                - group_width / 2
                + bar_width / 2
                for xi in x
            ]

            # ---------------------------------------------------------------
            # Barres
            # ---------------------------------------------------------------

            bars = ax.bar(
                positions,
                values,
                width=bar_width,
                label=LABELS[cfg],
                color=WONG[cfg],
                hatch=HATCHES[cfg],
                edgecolor="black",
                linewidth=0.5,
                zorder=3,
            )

            # ---------------------------------------------------------------
            # Pourcentage par rapport à ACP
            # ---------------------------------------------------------------

            for j, delay in enumerate(args.delay_order):

                # Ne rien afficher sur les barres ACP
                if cfg == "adaptive":
                    continue

                current_value = values[j]

                # Valeur ACP pour le même délai
                acp_value = acp_sub[value_col].get(
                    delay,
                    float("nan")
                )

                # -----------------------------------------------------------
                # Vérification des données
                # -----------------------------------------------------------

                if (
                    pd.isna(current_value)
                    or pd.isna(acp_value)
                    or acp_value == 0
                ):
                    continue

                # -----------------------------------------------------------
                # Calcul de la différence relative
                #
                # ((configuration - ACP) / ACP) * 100
                # -----------------------------------------------------------

                percentage = (
                    (current_value - acp_value)
                    / acp_value
                    * 100
                )

                # -----------------------------------------------------------
                # Position de l'annotation
                # -----------------------------------------------------------

                bar_height = bars[j].get_height()

                if bar_height >= 0:

                    xy_position = (
                        bars[j].get_x()
                        + bars[j].get_width() / 2,
                        bar_height
                    )

                    xy_offset = (0, 3)

                    vertical_alignment = "bottom"

                else:

                    xy_position = (
                        bars[j].get_x()
                        + bars[j].get_width() / 2,
                        bar_height
                    )

                    xy_offset = (0, -3)

                    vertical_alignment = "top"

                # -----------------------------------------------------------
                # Affichage du pourcentage
                #
                # Pourcentage volontairement discret
                # -----------------------------------------------------------

                ax.annotate(
                    f"{percentage:+.1f}%",
                    xy=xy_position,
                    xytext=xy_offset,
                    textcoords="offset points",
                    ha="center",
                    va=vertical_alignment,
                    fontsize=6,
                    fontweight="normal",
                    color=WONG[cfg],
                    rotation=90,
                    clip_on=False
                    
                )

        # -------------------------------------------------------------------
        # Titre du subplot
        # -------------------------------------------------------------------

        ax.set_title(
            title,
            fontsize=12,
            
            pad=5
        )

        # -------------------------------------------------------------------
        # Axe X
        # -------------------------------------------------------------------

        ax.set_xticks(x)

        ax.set_xticklabels(
            args.delay_order,
            fontsize=9
        )

        ax.set_xlabel(
            "Target inter-arrival time applied to all functions",
            fontsize=10.5,
            
            labelpad=7
        )

        # -------------------------------------------------------------------
        # Grille
        # -------------------------------------------------------------------

        ax.grid(
            axis="y",
            linestyle=":",
            linewidth=0.5,
            alpha=0.6,
            zorder=0,
        )

        ax.set_axisbelow(True)

        # -------------------------------------------------------------------
        # Ticks Y
        # -------------------------------------------------------------------

        ax.tick_params(
            axis="y",
            labelsize=9
        )

    # -----------------------------------------------------------------------
    # Labels Y
    # -----------------------------------------------------------------------

    axes[0].set_ylabel(
        "Energy (J/invocation)",
        fontsize=10.5,
        
    )

    axes[1].set_ylabel(
        "Peak power (W)",
        fontsize=10.5,
        
    )

    # -----------------------------------------------------------------------
    # Légende commune
    # -----------------------------------------------------------------------

    handles, labels = axes[0].get_legend_handles_labels()

    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.92),
        ncol=4,
        frameon=False,
        fontsize=8.5,
        handlelength=1.8,
        columnspacing=1.2,
    )

    # -----------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------

    fig.subplots_adjust(
        left=0.09,
        right=0.98,
        bottom=0.20,
        top=0.82,
        wspace=0.28,
    )

    # -----------------------------------------------------------------------
    # Sauvegarde
    # -----------------------------------------------------------------------

    out_dir = Path(args.out_dir)

    out_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    pdf_path = (
        out_dir /
        "energy_power_ML.pdf"
    )

    png_path = (
        out_dir /
        "energy_power_ML.png"
    )

    fig.savefig(
        pdf_path,
        bbox_inches="tight"
    )

    fig.savefig(
        png_path,
        dpi=300,
        bbox_inches="tight"
    )

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
            f"CSV introuvable : {csv_path}"
        )

    # -----------------------------------------------------------------------
    # Lecture du CSV
    # -----------------------------------------------------------------------

    df = pd.read_csv(csv_path)

    # -----------------------------------------------------------------------
    # Vérification des colonnes
    # -----------------------------------------------------------------------

    required_columns = {
        "config",
        "delay",
        "J_per_req_mean",
        "max_power_W",
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonnes manquantes dans le CSV : "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    # -----------------------------------------------------------------------
    # Nettoyage
    # -----------------------------------------------------------------------

    df["config"] = (
        df["config"]
        .astype(str)
        .str.strip()
    )

    df["delay"] = (
        df["delay"]
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------------------------
    # Vérification des configurations
    # -----------------------------------------------------------------------

    available_configs = set(
        df["config"].unique()
    )

    missing_configs = (
        set(args.config_order)
        - available_configs
    )

    if missing_configs:
        raise ValueError(
            "Configurations manquantes dans le CSV : "
            + ", ".join(
                sorted(missing_configs)
            )
        )

    # -----------------------------------------------------------------------
    # Génération de la figure
    # -----------------------------------------------------------------------

    plot_energy_power(
        df,
        args
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main(Args())
