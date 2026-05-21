#!/usr/bin/env python3
"""
Analysis — runs after main.py has populated data_cache.json.
Produces a 4-panel figure comparing all-arXiv vs AI/ML trends
and writes README.md.
"""

import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats

# ── Official arXiv monthly totals (arxiv.org/stats/get_monthly_submissions, May 2026)
OFFICIAL_TOTALS = {
    "2025-05": 24878, "2025-06": 24129, "2025-07": 23787, "2025-08": 21825,
    "2025-09": 26646, "2025-10": 27692, "2025-11": 23478, "2025-12": 25075,
    "2026-01": 23286, "2026-02": 24290, "2026-03": 30045, "2026-04": 28197,
}

BLUE   = "#2a6eb5"
ORANGE = "#d4631a"
GREEN  = "#1a8a4a"
PURPLE = "#7a3abf"
RED    = "#c0392b"

AIML_SETS_LABEL = "cs.AI ∪ cs.LG ∪ cs.CL ∪ stat.ML"


# ── Stats helpers ─────────────────────────────────────────────────────────────

def mk_test(series):
    t   = np.arange(len(series))
    res = stats.kendalltau(t, np.array(series, dtype=float))
    return float(res.statistic), float(res.pvalue)  # type: ignore[union-attr]


def ols(series):
    t   = np.arange(len(series), dtype=float)
    res = stats.linregress(t, np.array(series, dtype=float))
    return float(res.slope), float(res.intercept), float(res.rvalue**2), float(res.pvalue)  # type: ignore[union-attr]


def stat_dict(series):
    sl, ic, r2, p = ols(series)
    tau, mkp      = mk_test(series)
    return dict(slope=sl, intercept=ic, r2=r2, p=p, mk_tau=tau, mk_p=mkp)


def sig(p):
    return "**significant** (p < 0.05)" if p < 0.05 else "not significant (p ≥ 0.05)"


# ── Plotting ──────────────────────────────────────────────────────────────────

def _panel(ax, x, vals, color, title, ylabel, sd, pct_fmt=False):
    ax.bar(x, vals, color=color, alpha=0.72, zorder=2)
    trend = sd["slope"] * x + sd["intercept"]
    lbl = (f"OLS  slope={sd['slope']:+.1f}/mo  R²={sd['r2']:.2f}  p={sd['p']:.3f}")
    ax.plot(x, trend, "--", color=RED, lw=2, zorder=3, label=lbl)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=5)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.3, zorder=1)
    fmt = (mticker.FuncFormatter(lambda v, _: f"{v:.1f}%") if pct_fmt
           else mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.yaxis.set_major_formatter(fmt)
    mk_txt = f"Mann-Kendall  τ = {sd['mk_tau']:.3f}   p = {sd['mk_p']:.3f}"
    ax.text(0.99, 0.96, mk_txt, transform=ax.transAxes,
            fontsize=8, va="top", ha="right", color="darkred",
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="#999", alpha=0.85))


def make_figure(df_all: pd.DataFrame, df_aiml: pd.DataFrame):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True)
    x     = np.arange(len(df_all))
    xlabs = df_all["label"].tolist()

    ratio_all  = df_all["ratio"].values.astype(float) * 100
    ratio_aiml = (df_aiml["unique_in_sample"].values.astype(float) /
                  df_aiml["sample_size"].values.astype(float) * 100)

    # ── Panel A: total papers all-arXiv (official) ───────────────────────────
    _panel(axes[0, 0], x,
           df_all["total_papers"].values,
           ORANGE,
           "All arXiv — total papers (official counts)",
           "Papers / month",
           stat_dict(df_all["total_papers"].values))

    # ── Panel B: estimated unique submitters all-arXiv ───────────────────────
    _panel(axes[0, 1], x,
           df_all["est_unique"].values,
           BLUE,
           "All arXiv — estimated unique submitters\n"
           "(sample uniqueness ratio × official total)",
           "Est. unique submitters / month",
           stat_dict(df_all["est_unique"].values))

    # ── Panel C: uniqueness ratio comparison ─────────────────────────────────
    ax = axes[1, 0]
    ax.plot(x, ratio_all,  "o-", color=BLUE,   lw=2, ms=6, label="All arXiv")
    ax.plot(x, ratio_aiml, "s-", color=PURPLE, lw=2, ms=6, label=f"AI/ML")
    sd_ra = stat_dict(ratio_all);  sd_rm = stat_dict(ratio_aiml)
    ax.plot(x, sd_ra["slope"]*x + sd_ra["intercept"],  "--", color=BLUE,   lw=1.5, alpha=0.7)
    ax.plot(x, sd_rm["slope"]*x + sd_rm["intercept"],  "--", color=PURPLE, lw=1.5, alpha=0.7)
    ax.set_ylabel("% unique submitters in sample", fontsize=10)
    ax.set_title("Uniqueness ratio: all arXiv vs AI/ML\n"
                 "(unique submitters ÷ sample)", fontsize=11, fontweight="bold", pad=5)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}%"))
    # Annotate OLS slopes in the corner
    txt = (f"All arXiv  slope={sd_ra['slope']*100:+.4f}%/mo  p={sd_ra['p']:.3f}\n"
           f"AI/ML      slope={sd_rm['slope']*100:+.4f}%/mo  p={sd_rm['p']:.3f}")
    ax.text(0.02, 0.05, txt, transform=ax.transAxes, fontsize=8,
            va="bottom", color="black",
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="#999", alpha=0.85))

    # ── Panel D: AI/ML unique first authors (raw, note variable sample size) ──
    _panel(axes[1, 1], x,
           df_aiml["unique_in_sample"].values,
           PURPLE,
           f"AI/ML ({AIML_SETS_LABEL})\nunique submitters in sample (variable sample size)",
           "Unique submitters in sample",
           stat_dict(df_aiml["unique_in_sample"].values.astype(float)))
    # Overlay sample-size markers
    ax2 = axes[1, 1].twinx()
    ax2.plot(x, df_aiml["sample_size"].values, "^--", color="gray",
             lw=1, ms=5, alpha=0.7, label="sample size")
    ax2.set_ylabel("Sample size", fontsize=9, color="gray")
    ax2.tick_params(axis="y", labelcolor="gray")
    ax2.legend(fontsize=8, loc="upper right")

    for col in range(2):
        axes[1, col].set_xticks(x)
        axes[1, col].set_xticklabels(xlabs, rotation=45, ha="right", fontsize=9)

    fig.suptitle(
        "arXiv contributor growth  ·  May 2025 – April 2026\n"
        "Hypothesis: Gen AI is driving an explosion of new submitters",
        fontsize=13, y=1.01)

    plt.tight_layout()
    plt.savefig("figure.png", dpi=150, bbox_inches="tight")
    print("Figure saved → figure.png")


# (README is written manually — see README.md)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists("data_cache.json"):
        print("data_cache.json not found — run main.py first.")
        return

    with open("data_cache.json") as f:
        cache = json.load(f)

    months = sorted(k for k in cache if k in OFFICIAL_TOTALS)
    aiml_months = sorted(k for k in cache if k.endswith("-aiml"))

    if len(months) < 12:
        print(f"Only {len(months)}/12 all-arXiv months cached.")
    if len(aiml_months) < 12:
        print(f"Only {len(aiml_months)}/12 AI/ML months cached — run main.py first.")
        return

    # ── Build all-arXiv DataFrame ────────────────────────────────────────────
    rows_all = []
    for key in months:
        r = cache[key]
        sample    = r["sample_size"]
        unique    = r["unique_in_sample"]
        total_off = OFFICIAL_TOTALS[key]
        ratio     = unique / sample if sample > 0 else 0.0
        rows_all.append({
            "label":         key,
            "total_papers":  total_off,
            "sample_size":   sample,
            "unique_sample": unique,
            "ratio":         ratio,
            "est_unique":    int(ratio * total_off),
        })
    df_all = pd.DataFrame(rows_all)

    # ── Build AI/ML DataFrame ────────────────────────────────────────────────
    rows_aiml = []
    for key in aiml_months:
        r    = cache[key]
        base = key.replace("-aiml", "")
        rows_aiml.append({
            "label":            base,
            "sample_size":      r["sample_size"],
            "unique_in_sample": r["unique_in_sample"],
        })
    df_aiml = pd.DataFrame(rows_aiml)

    # ── Print summary ────────────────────────────────────────────────────────
    print("\n── All arXiv ─────────────────────────────────────────")
    print(df_all[["label","total_papers","unique_sample","est_unique"]].to_string())

    print("\n── AI/ML sample ──────────────────────────────────────")
    print(df_aiml.to_string())

    ratio_all  = df_all["ratio"].values.astype(float)
    ratio_aiml = (df_aiml["unique_in_sample"].values.astype(float) /
                  df_aiml["sample_size"].values.astype(float))

    sd_tot   = stat_dict(df_all["total_papers"].values)
    sd_all   = stat_dict(df_all["est_unique"].values)
    sd_aiml  = stat_dict(df_aiml["unique_in_sample"].values.astype(float))
    sd_asize = stat_dict(df_aiml["sample_size"].values.astype(float))
    sd_ra    = stat_dict(ratio_all)
    sd_rm    = stat_dict(ratio_aiml)

    print(f"\n── Trend: total papers (all arXiv) ───────────────────")
    print(f"  OLS  slope={sd_tot['slope']:+.0f}/mo  R²={sd_tot['r2']:.3f}  p={sd_tot['p']:.4f}")
    print(f"  MK   τ={sd_tot['mk_tau']:.3f}  p={sd_tot['mk_p']:.4f}")

    print(f"\n── Trend: est. unique submitters (all arXiv) ─────────")
    print(f"  OLS  slope={sd_all['slope']:+.0f}/mo  R²={sd_all['r2']:.3f}  p={sd_all['p']:.4f}")
    print(f"  MK   τ={sd_all['mk_tau']:.3f}  p={sd_all['mk_p']:.4f}")

    print(f"\n── Trend: unique first authors (AI/ML, raw) ──────────")
    print(f"  OLS  slope={sd_aiml['slope']:+.1f}/mo  R²={sd_aiml['r2']:.3f}  p={sd_aiml['p']:.4f}")
    print(f"  MK   τ={sd_aiml['mk_tau']:.3f}  p={sd_aiml['mk_p']:.4f}")

    print(f"\n── Trend: uniqueness ratio (AI/ML) ───────────────────")
    print(f"  mean={ratio_aiml.mean()*100:.2f}%  std={ratio_aiml.std()*100:.2f}%")
    print(f"  OLS  slope={sd_rm['slope']*100:+.5f}%/mo  R²={sd_rm['r2']:.3f}  p={sd_rm['p']:.4f}")
    print(f"  MK   τ={sd_rm['mk_tau']:.3f}  p={sd_rm['mk_p']:.4f}")

    print(f"\n── Trend: uniqueness ratio (all arXiv) ───────────────")
    print(f"  mean={ratio_all.mean()*100:.2f}%  std={ratio_all.std()*100:.2f}%")
    print(f"  OLS  slope={sd_ra['slope']*100:+.5f}%/mo  R²={sd_ra['r2']:.3f}  p={sd_ra['p']:.4f}")
    print(f"  MK   τ={sd_ra['mk_tau']:.3f}  p={sd_ra['mk_p']:.4f}")

    df_all.to_csv("results_all.csv", index=False)
    df_aiml.to_csv("results_aiml.csv", index=False)
    print("\nData saved → results_all.csv, results_aiml.csv")

    make_figure(df_all, df_aiml)

    # ── Exhaustive per-category data (optional) ──────────────────────────────
    CATS = ["cs.LG", "cs.SE"]
    exh_keys = {cat: sorted(k for k in cache if k.endswith(f"-{cat}"))
                for cat in CATS}
    have_exhaustive = all(len(exh_keys[c]) == 12 for c in CATS)

    if have_exhaustive:
        dfs_exh = {}
        for cat in CATS:
            rows = []
            for key in exh_keys[cat]:
                r = cache[key]
                base = key[: -len(f"-{cat}")]
                rows.append({
                    "label":          base,
                    "total_papers":   r["total_papers"],
                    "unique_authors": r["unique_authors"],
                    "ratio":          r["unique_authors"] / r["total_papers"]
                                      if r["total_papers"] else 0.0,
                })
            dfs_exh[cat] = pd.DataFrame(rows)

        print("\n── Exhaustive: cs.LG ─────────────────────────────────")
        print(dfs_exh["cs.LG"].to_string())
        print("\n── Exhaustive: cs.SE ─────────────────────────────────")
        print(dfs_exh["cs.SE"].to_string())

        for cat in CATS:
            df_c = dfs_exh[cat]
            sd_u = stat_dict(df_c["unique_authors"].values.astype(float))
            sd_t = stat_dict(df_c["total_papers"].values.astype(float))
            sd_r = stat_dict(df_c["ratio"].values.astype(float))
            print(f"\n── Trend ({cat}): total papers ────────────────────")
            print(f"  OLS slope={sd_t['slope']:+.1f}/mo  R²={sd_t['r2']:.3f}  p={sd_t['p']:.4f}")
            print(f"  MK  τ={sd_t['mk_tau']:.3f}  p={sd_t['mk_p']:.4f}")
            print(f"── Trend ({cat}): unique first authors ────────────")
            print(f"  OLS slope={sd_u['slope']:+.1f}/mo  R²={sd_u['r2']:.3f}  p={sd_u['p']:.4f}")
            print(f"  MK  τ={sd_u['mk_tau']:.3f}  p={sd_u['mk_p']:.4f}")
            print(f"── Trend ({cat}): uniqueness ratio ────────────────")
            print(f"  mean={df_c['ratio'].mean()*100:.2f}%  "
                  f"OLS slope={sd_r['slope']*100:+.4f}%/mo  "
                  f"p={sd_r['p']:.4f}")

        make_exhaustive_figure(dfs_exh)
    else:
        missing = {c: 12 - len(exh_keys[c]) for c in CATS if len(exh_keys[c]) < 12}
        print(f"\nExhaustive data not yet complete: {missing}")
        print("Run  python collect_exhaustive.py  then re-run analyze.py")


def make_exhaustive_figure(dfs_exh: dict):
    """2-panel figure: cs.SE and cs.LG unique authors (exhaustive counts)."""
    CATS   = ["cs.SE", "cs.LG"]
    COLORS = {"cs.LG": PURPLE, "cs.SE": GREEN}

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, cat in zip(axes, CATS):
        df   = dfs_exh[cat]
        x    = np.arange(len(df))
        sd_u = stat_dict(df["unique_authors"].values.astype(float))
        sd_t = stat_dict(df["total_papers"].values.astype(float))

        ax.bar(x, df["unique_authors"].values, color=COLORS[cat], alpha=0.72, zorder=2,
               label="Unique submitters")
        ax.bar(x, df["total_papers"].values, color="lightgray", alpha=0.5, zorder=1,
               label="Total papers")

        trend_u = sd_u["slope"] * x + sd_u["intercept"]
        ax.plot(x, trend_u, "--", color=RED, lw=2, zorder=3,
                label=(f"OLS unique  slope={sd_u['slope']:+.1f}/mo  "
                       f"R²={sd_u['r2']:.2f}  p={sd_u['p']:.3f}"))

        ax.set_title(f"{cat} — exhaustive unique submitters per month",
                     fontsize=11, fontweight="bold")
        ax.set_ylabel("Count", fontsize=10)
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(axis="y", alpha=0.3, zorder=1)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

        mk_txt = (f"Mann-Kendall  τ = {sd_u['mk_tau']:.3f}   "
                  f"p = {sd_u['mk_p']:.3f}")
        ax.text(0.99, 0.96, mk_txt, transform=ax.transAxes,
                fontsize=8, va="top", ha="right", color="darkred",
                bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow",
                          ec="#999", alpha=0.85))

        ax.set_xticks(x)
        ax.set_xticklabels(df["label"].tolist(), rotation=45,
                           ha="right", fontsize=9)

    fig.suptitle(
        "arXiv exhaustive unique submitters per month  ·  May 2025 – April 2026\n"
        "cs.SE (Software Engineering) and cs.LG (Machine Learning)",
        fontsize=12, y=1.01)
    plt.tight_layout()
    plt.savefig("figure_exhaustive.png", dpi=150, bbox_inches="tight")
    print("Figure saved → figure_exhaustive.png")


if __name__ == "__main__":
    main()
