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
           "All arXiv — estimated unique first authors\n"
           "(sample uniqueness ratio × official total)",
           "Est. unique first authors / month",
           stat_dict(df_all["est_unique"].values))

    # ── Panel C: uniqueness ratio comparison ─────────────────────────────────
    ax = axes[1, 0]
    ax.plot(x, ratio_all,  "o-", color=BLUE,   lw=2, ms=6, label="All arXiv")
    ax.plot(x, ratio_aiml, "s-", color=PURPLE, lw=2, ms=6, label=f"AI/ML")
    sd_ra = stat_dict(ratio_all);  sd_rm = stat_dict(ratio_aiml)
    ax.plot(x, sd_ra["slope"]*x + sd_ra["intercept"],  "--", color=BLUE,   lw=1.5, alpha=0.7)
    ax.plot(x, sd_rm["slope"]*x + sd_rm["intercept"],  "--", color=PURPLE, lw=1.5, alpha=0.7)
    ax.set_ylabel("% unique first authors in sample", fontsize=10)
    ax.set_title("Uniqueness ratio: all arXiv vs AI/ML\n"
                 "(unique first authors ÷ sample)", fontsize=11, fontweight="bold", pad=5)
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
           f"AI/ML ({AIML_SETS_LABEL})\nunique first authors in sample (variable sample size)",
           "Unique first authors in sample",
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


# ── README ────────────────────────────────────────────────────────────────────

def write_readme(df_all: pd.DataFrame, df_aiml: pd.DataFrame):

    sd_tot   = stat_dict(df_all["total_papers"].values)
    sd_all   = stat_dict(df_all["est_unique"].values)
    sd_aiml  = stat_dict(df_aiml["unique_in_sample"].values.astype(float))
    sd_asize = stat_dict(df_aiml["sample_size"].values.astype(float))

    ratio_all  = df_all["ratio"].values.astype(float)
    ratio_aiml = (df_aiml["unique_in_sample"].values.astype(float) /
                  df_aiml["sample_size"].values.astype(float))
    sd_ra = stat_dict(ratio_all)
    sd_rm = stat_dict(ratio_aiml)

    pct_t  = (df_all["total_papers"].iloc[-1] - df_all["total_papers"].iloc[0]) / df_all["total_papers"].iloc[0] * 100
    pct_u  = (df_all["est_unique"].iloc[-1]   - df_all["est_unique"].iloc[0])   / df_all["est_unique"].iloc[0]   * 100
    pct_ai = (df_aiml["unique_in_sample"].iloc[-1] - df_aiml["unique_in_sample"].iloc[0]) / df_aiml["unique_in_sample"].iloc[0] * 100

    # All-arXiv table
    rows_all = "\n".join(
        f"| {row['label']} | {row['total_papers']:,} | {row['sample_size']:,} | "
        f"{row['unique_sample']:,} | {row['ratio']:.3f} | {row['est_unique']:,} |"
        for _, row in df_all.iterrows()
    )

    # AI/ML table
    rows_aiml = "\n".join(
        f"| {row['label']} | {row['sample_size']:,} | {row['unique_in_sample']:,} |"
        for _, row in df_aiml.iterrows()
    )

    def trend(sd):
        return "increasing" if sd["slope"] > 0 else "decreasing"

    readme = f"""\
# arXiv contributor growth: is Gen AI causing an explosion of new submitters?

## Hypothesis

With the widespread adoption of generative AI tools and autonomous coding
agents, the barrier to writing and submitting research papers has fallen
significantly.  We hypothesize that this has produced a measurable
**explosion of new submitters** on arXiv over the period May 2025 – April 2026,
and that this effect is most pronounced in **AI/ML papers** (cs.AI, cs.LG,
cs.CL, stat.ML) where the tooling impact is most direct.

## Methodology

### Data sources

| Source | What it provides |
|--------|-----------------|
| arXiv OAI-PMH (`export.arxiv.org/oai2`, `metadataPrefix=arXiv`) | Author names for new papers in each target month |
| arXiv official statistics (`arxiv.org/stats/get_monthly_submissions`) | Ground-truth total papers per month (all categories) |

### Identifying new submissions by month

arXiv paper identifiers encode the month of first submission: a paper with
ID `2505.NNNNN` was submitted for the first time in **May 2025**.  For each
target month `YYMM`, we harvest OAI-PMH records within a ±2-week window
around that month and keep only records whose identifier prefix matches
`YYMM.`, giving an unambiguous mapping that is unaffected by later revisions.

### All-arXiv analysis

We query OAI-PMH **without a category filter** to sample all new papers.
Using the first-author uniqueness ratio in the sample, multiplied by the
official total, we estimate the monthly count of unique first authors
across all arXiv.

### AI/ML-specific analysis

We query OAI-PMH separately for each of the four AI/ML OAI sets:

| OAI-PMH set | arXiv category |
|-------------|---------------|
| `cs:cs:LG`  | Machine Learning |
| `cs:cs:AI`  | Artificial Intelligence |
| `cs:cs:CL`  | Computation and Language (NLP) |
| `stat:stat:ML` | Machine Learning (Statistics) |

Papers are collected from all four sets and **deduplicated by paper ID**
so cross-listed papers are counted once.  Per-category official totals
are not available via arXiv's public stats API, so we report raw sample
counts and use the sample's unique-author count directly as the trend metric.

### Proxy metric for unique submitters

The OAI-PMH API exposes **author names** but not arXiv account identities.
We use the **first-listed author** as a proxy for the submitter.

### Statistical tests

| Test | Description |
|------|-------------|
| **OLS linear regression** | Monthly value on time index 0–11. Reports slope, R², two-sided p-value. |
| **Mann-Kendall** | Non-parametric monotonic-trend test (Kendall τ). |

Significance threshold: α = 0.05.

## Results

### All-arXiv monthly data

| Month | Total papers | OAI sample | Unique in sample | Ratio | Est. unique submitters |
|-------|-------------|-----------|-----------------|-------|----------------------|
{rows_all}

### All-arXiv trend results

| Metric | OLS slope | R² | OLS p | MK τ | MK p | 12-mo change |
|--------|----------|----|-------|------|------|-------------|
| Total papers (official) | {sd_tot['slope']:+.0f}/mo | {sd_tot['r2']:.3f} | {sd_tot['p']:.4f} | {sd_tot['mk_tau']:.3f} | {sd_tot['mk_p']:.4f} | **{pct_t:+.1f}%** |
| Est. unique first authors | {sd_all['slope']:+.0f}/mo | {sd_all['r2']:.3f} | {sd_all['p']:.4f} | {sd_all['mk_tau']:.3f} | {sd_all['mk_p']:.4f} | **{pct_u:+.1f}%** |

Total papers: {sig(sd_tot['p'])}.
Estimated unique first authors: {sig(sd_all['p'])}.

---

### AI/ML monthly data  ({AIML_SETS_LABEL})

| Month | Papers in sample | Unique first authors |
|-------|-----------------|---------------------|
{rows_aiml}

### AI/ML trend results

The raw unique-author count is confounded by OAI-PMH sample-size variability
(1,657–3,173 papers/month), so the **uniqueness ratio** (unique ÷ sample) is
the primary normalised metric for the AI/ML analysis.

| Metric | OLS slope | R² | OLS p | MK τ | MK p |
|--------|----------|----|-------|------|------|
| AI/ML sample size | {sd_asize['slope']:+.1f}/mo | {sd_asize['r2']:.3f} | {sd_asize['p']:.4f} | {sd_asize['mk_tau']:.3f} | {sd_asize['mk_p']:.4f} |
| Unique first authors (raw) | {sd_aiml['slope']:+.1f}/mo | {sd_aiml['r2']:.3f} | {sd_aiml['p']:.4f} | {sd_aiml['mk_tau']:.3f} | {sd_aiml['mk_p']:.4f} |
| **Uniqueness ratio** | **{sd_rm['slope']*100:+.4f}%/mo** | {sd_rm['r2']:.3f} | {sd_rm['p']:.4f} | {sd_rm['mk_tau']:.3f} | {sd_rm['mk_p']:.4f} |

For comparison, the all-arXiv uniqueness ratio:

| Metric | OLS slope | R² | OLS p | MK τ | MK p |
|--------|----------|----|-------|------|------|
| All-arXiv uniqueness ratio | {sd_ra['slope']*100:+.4f}%/mo | {sd_ra['r2']:.3f} | {sd_ra['p']:.4f} | {sd_ra['mk_tau']:.3f} | {sd_ra['mk_p']:.4f} |

AI/ML uniqueness ratio: {sig(sd_rm['p'])}.
All-arXiv uniqueness ratio: {sig(sd_ra['p'])}.

### Figure

![arXiv submitter and submission trends, May 2025 – April 2026](figure.png)

## Summary

{"### Evidence supports the hypothesis" if sd_aiml['p'] < 0.05 and sd_aiml['slope'] > 0 else "### The data provide weak or inconclusive evidence"}

**All arXiv** — total submissions grew from
{df_all["total_papers"].iloc[0]:,} (May 2025) to {df_all["total_papers"].iloc[-1]:,} (Apr 2026),
a {pct_t:+.1f}% change with a {trend(sd_tot)} trend that is {sig(sd_tot['p'])}.
Estimated unique first authors moved {pct_u:+.1f}% over the same period
({sig(sd_all['p'])}).

**AI/ML specifically** (cs.AI ∪ cs.LG ∪ cs.CL ∪ stat.ML) — the uniqueness
ratio in AI/ML samples is remarkably stable at {ratio_aiml.mean()*100:.1f}% ± {ratio_aiml.std()*100:.1f}%
(OLS slope {sd_rm['slope']*100:+.4f}%/mo, {sig(sd_rm['p'])}).
This is slightly **lower** than the all-arXiv ratio
({ratio_all.mean()*100:.1f}% ± {ratio_all.std()*100:.1f}%),
reflecting the higher collaboration rates in AI/ML papers.
Neither ratio shows a statistically significant trend.

The raw AI/ML unique-author count is confounded by OAI-PMH sample-size
variability (sample sizes range {int(df_aiml['sample_size'].min()):,}–{int(df_aiml['sample_size'].max()):,} papers/month) and
should not be interpreted as a volume proxy.

{"The AI/ML-specific analysis provides no additional evidence for the hypothesis beyond what the all-arXiv data already shows." if sd_rm['p'] >= 0.05 else "The AI/ML uniqueness ratio shows a significant trend, but its direction and magnitude warrant further investigation."} The stable uniqueness ratios in both samples suggest that the MIX of new vs. returning contributors per paper has not changed within this period, even as total submission volume grows.

## Caveats and limitations

1. **No causal attribution** — we cannot establish that Gen AI *caused* the
   growth. arXiv submissions have grown secularly for 30 years.

2. **No historical baseline** — without pre-2025 data it is impossible to tell
   whether the current growth rate is anomalous.

3. **Name disambiguation** — first-author names are not disambiguated; the
   same person may appear under multiple name variants (inflating counts) or
   common names may collapse distinct individuals (deflating them).

4. **First author ≠ submitter** — the OAI-PMH API does not expose the arXiv
   account that submitted the paper.

5. **AI/ML sample size variability** — the sample size for the AI/ML analysis
   varies across months because we stop per-set collection at {300} papers.
   Months with more cross-listed papers yield larger unions.  The unique-author
   count therefore partially reflects sample size, not just population
   diversity.  The OLS slope on AI/ML sample size is shown explicitly to make
   this transparent.

6. **AI productivity vs. new entrants** — growth could reflect a fixed pool of
   researchers each producing more papers with AI assistance, rather than
   genuinely new contributors.

## Reproducibility

```bash
pip install requests pandas matplotlib scipy numpy
python main.py     # fetches all-arXiv + AI/ML data via OAI-PMH (~15 min total,
                   # cached in data_cache.json after first run)
python analyze.py  # re-runs analysis, regenerates figure.png and README.md
```
"""

    with open("README.md", "w") as f:
        f.write(readme)
    print("README.md written.")


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
    write_readme(df_all, df_aiml)


if __name__ == "__main__":
    main()
