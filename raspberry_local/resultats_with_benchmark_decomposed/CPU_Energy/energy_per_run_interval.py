"""
energy_per_run_interval.py

Calcule, pour chaque repetition labellisee (via antela_logger_v2.py + mark_run.py) :
  - duration_s        : duree de l'intervalle [debut(repN), debut(repN+1))
  - idle_power_local_W: baseline idle mesuree localement dans cet intervalle (verification)
  - energy_total_J    : energie nette (baseline soustraite) sur l'intervalle
  - J_per_req         : energie totale / nb de requetes du run

Methode : fenetre = [debut du label repN, debut du label rep(N+1)) — capture le run
complet + sa traine de refroidissement, jusqu'au lancement du run suivant.

Compatible Jupyter (class Args). Fonctionne sur un ou plusieurs fichiers CSV
labellises concatenes (ex: plusieurs sessions antela_data_*.csv).
"""
import pandas as pd
import glob

REQUESTS_PER_RUN = 2000


class Args:
    csv_glob = "/mnt/user-data/uploads/antela_data_*.csv"  # un ou plusieurs fichiers
    config_name = "local"        # "local", "1core", "apiserver", "adaptive"...
    idle_labels = ("idle", "unknown")
    output_csv = None            # auto si None


def load_all(csv_glob: str) -> pd.DataFrame:
    files = sorted(glob.glob(csv_glob))
    if not files:
        raise FileNotFoundError(f"Aucun fichier ne correspond a {csv_glob}")
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df["Power_W"] = pd.to_numeric(df["Power_W"], errors="coerce")
        df = df.dropna(subset=["Power_W"])
        df["ts"] = pd.to_datetime(df["Date"] + " " + df["Time"])
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True).sort_values("ts").reset_index(drop=True)


def compute_per_run(df: pd.DataFrame, idle_labels, requests_per_run: int) -> pd.DataFrame:
    is_idle = df["Label"].isin(idle_labels)
    global_baseline = df.loc[is_idle, "Power_W"].median()

    active_labels = sorted(df.loc[~is_idle, "Label"].unique())
    starts = {lab: df.loc[df["Label"] == lab, "ts"].iloc[0] for lab in active_labels}
    ordered = sorted(starts.items(), key=lambda kv: kv[1])

    rows = []
    for i, (label, start_ts) in enumerate(ordered):
        end_ts = ordered[i + 1][1] if i + 1 < len(ordered) else df["ts"].iloc[-1]
        window = df[(df["ts"] >= start_ts) & (df["ts"] < end_ts)]

        idle_in_window = window[window["Label"].isin(idle_labels)]
        idle_power_local = (
            idle_in_window["Power_W"].median() if len(idle_in_window) else float("nan")
        )

        energy_net_J = (window["Power_W"] - global_baseline).clip(lower=0).sum() * 1
        dur_s = (
            (window["ts"].iloc[-1] - window["ts"].iloc[0]).total_seconds() + 1
            if len(window) else 0
        )

        # extrait le "delai" du label si le format est <config>_<delai>_repN
        parts = label.split("_")
        delay = parts[1] if len(parts) >= 3 else "unknown"

        rows.append({
            "label": label,
            "delay": delay,
            "duration_s": dur_s,
            "idle_power_local_W": round(idle_power_local, 2) if idle_power_local == idle_power_local else None,
            "energy_total_J": round(energy_net_J, 2),
            "J_per_req": round(energy_net_J / requests_per_run, 4),
        })

    per_run = pd.DataFrame(rows)
    delay_order = {"10ms": 0, "50ms": 1, "100ms": 2, "200ms": 3, "1s": 4}
    per_run["_order"] = per_run["delay"].map(delay_order).fillna(99)
    per_run = per_run.sort_values(["_order", "label"]).drop(columns="_order")
    return per_run, global_baseline


def summarize(per_run: pd.DataFrame) -> pd.DataFrame:
    summary = per_run.groupby("delay").agg(
        n_runs=("J_per_req", "count"),
        max_power_local_idle_W=("idle_power_local_W", "max"),
        energy_total_J=("energy_total_J", "sum"),
        J_per_req_mean=("J_per_req", "mean"),
        J_per_req_std=("J_per_req", "std"),
    )
    order = ["10ms", "50ms", "100ms", "200ms", "1s"]
    return summary.reindex([d for d in order if d in summary.index])


def main(args: Args):
    df = load_all(args.csv_glob)
    per_run, baseline = compute_per_run(df, args.idle_labels, REQUESTS_PER_RUN)

    print(f"Config: {args.config_name}")
    print(f"Baseline globale: {baseline:.2f} W\n")
    print(per_run.to_string(index=False))

    summary = summarize(per_run)
    print(f"\n--- Resume par delai ---")
    print(summary.to_string())

    out_per_run = args.output_csv or f"/mnt/user-data/outputs/{args.config_name}_per_run_detail.csv"
    out_summary = out_per_run.replace(".csv", "_summary.csv")
    per_run.to_csv(out_per_run, index=False)
    summary.to_csv(out_summary)
    print(f"\nSauvegarde -> {out_per_run}")
    print(f"Sauvegarde -> {out_summary}")

    return per_run, summary


if __name__ == "__main__":
    main(Args())
