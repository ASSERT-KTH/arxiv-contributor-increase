#!/usr/bin/env python3
"""
Hypothesis: With Gen AI and agents, there is an explosion of new submitters on arXiv.

Methodology:
- arXiv paper IDs encode their submission month: a paper ID like 2505.NNNNN was
  submitted in May 2025.  We use the arXiv OAI-PMH harvest API to collect
  papers whose IDs match the YYMM prefix for each target month, giving an
  unambiguous mapping between a paper and the month it was first submitted.
- For each of the 12 complete months (May 2025 – April 2026) we collect up to
  TARGET_SAMPLE papers with the matching ID prefix.
- We record the unique first-author names and the total number of papers
  submitted that month (estimated from the sequence numbers in the IDs).
- Statistical trend tests are then applied to both series.
"""

import requests
import xml.etree.ElementTree as ET
import time
import json
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats


# ── Constants ────────────────────────────────────────────────────────────────

CACHE_FILE    = "data_cache.json"
OAI_URL       = "https://export.arxiv.org/oai2"
TARGET_SAMPLE = 500   # new papers per month we aim to collect (all-categories)
TARGET_AIML   = 300   # new papers per AI/ML set before deduplication
REQUEST_WAIT  = 4.0   # seconds between API calls
HEADERS       = {"User-Agent": "arxiv-submitter-study/1.0 (martin2020+claude@monperrus.net)"}

# AI/ML OAI-PMH sets to query (union, deduplicating by paper ID)
AIML_SETS = ["cs:cs:LG", "cs:cs:AI", "cs:cs:CL", "stat:stat:ML"]

OAI_NS  = "http://www.openarchives.org/OAI/2.0/"
ARX_NS  = "http://arxiv.org/OAI/arXiv/"


# ── OAI-PMH helpers ──────────────────────────────────────────────────────────

def oai_list_records(from_date: str, until_date: str,
                     resumption_token: str | None = None,
                     oai_set: str | None = None):
    """
    Fetch one page of OAI-PMH ListRecords.
    Returns (records_list, next_token_or_None).
    """
    if resumption_token:
        params = {"verb": "ListRecords", "resumptionToken": resumption_token}
    else:
        params = {
            "verb": "ListRecords",
            "from": from_date,
            "until": until_date,
            "metadataPrefix": "arXiv",
        }
        if oai_set:
            params["set"] = oai_set

    time.sleep(REQUEST_WAIT)
    resp = requests.get(OAI_URL, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    root    = ET.fromstring(resp.text)
    records = root.findall(f".//{{{OAI_NS}}}record")

    tok_el = root.find(f".//{{{OAI_NS}}}resumptionToken")
    next_token = tok_el.text if (tok_el is not None and tok_el.text) else None

    return records, next_token


def extract_first_author(record) -> str | None:
    """Return 'Lastname, Firstname' or None from an OAI record."""
    meta = record.find(f".//{{{ARX_NS}}}arXiv")
    if meta is None:
        return None
    keynames  = meta.findall(f".//{{{ARX_NS}}}keyname")
    forenames = meta.findall(f".//{{{ARX_NS}}}forenames")
    if not keynames:
        return None
    kn = (keynames[0].text  or "").strip()
    fn = (forenames[0].text if forenames else "").strip()
    return f"{kn}, {fn}" if fn else kn


def record_arxiv_id(record) -> str | None:
    ident_el = record.find(f"{{{OAI_NS}}}header/{{{OAI_NS}}}identifier")
    if ident_el is None or not ident_el.text:
        return None
    # "oai:arXiv.org:2505.01234" → "2505.01234"
    return ident_el.text.split(":")[-1]


# ── Data collection ──────────────────────────────────────────────────────────

def yymm(year: int, month: int) -> str:
    """Return the 4-char arXiv ID prefix, e.g. '2505'."""
    return f"{year % 100:02d}{month:02d}"


def collect_month(year: int, month: int) -> dict:
    """
    Harvest OAI-PMH records for one month.
    Strategy: query a 10-week window centred on the target month;
    keep only records whose arXiv ID starts with the YYMM prefix.
    Stop once we have TARGET_SAMPLE papers.
    """
    prefix = yymm(year, month)
    # Wider window to catch last-week submissions announced the following Monday
    from_date = (date(year, month, 1) - timedelta(days=7)).isoformat()
    next_m = date(year + (month == 12), month % 12 + 1, 1)
    until_date = (next_m + timedelta(days=14)).isoformat()

    authors: list[str] = []
    seq_numbers: list[int] = []   # to estimate total papers in month
    token = None
    page  = 0

    while len(authors) < TARGET_SAMPLE:
        try:
            records, token = oai_list_records(from_date, until_date, token)
        except Exception as exc:
            print(f"    OAI error: {exc}")
            break

        page += 1
        for rec in records:
            arxiv_id = record_arxiv_id(rec)
            if arxiv_id and arxiv_id.startswith(f"{prefix}."):
                author = extract_first_author(rec)
                if author:
                    authors.append(author)
                # Collect sequence number to estimate total papers
                try:
                    seq_numbers.append(int(arxiv_id.split(".")[-1]))
                except ValueError:
                    pass

        print(f"    page {page}: {len(authors)} new-month papers collected", flush=True)

        if token is None:
            break  # no more pages

    # Estimate total papers submitted that month from the maximum sequence number
    # (arXiv sequence numbers are assigned sequentially per month)
    estimated_total = max(seq_numbers) if seq_numbers else 0

    return {
        "year":             year,
        "month":            month,
        "sample_size":      len(authors),
        "unique_in_sample": len(set(authors)),
        "estimated_total":  estimated_total,
        "authors":          authors,
    }


def collect_all() -> dict:
    cache: dict = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)

    # 12 complete months: May 2025 – April 2026
    months = []
    y, m = 2025, 5
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    results = {}
    for year, month in months:
        key = f"{year}-{month:02d}"
        if key in cache:
            r = cache[key]
            print(f"[cache] {key}: {r['unique_in_sample']} unique / "
                  f"~{r['estimated_total']:,} total papers")
            results[key] = r
            continue

        print(f"[fetch] {key} (prefix {yymm(year,month)})…")
        rec = collect_month(year, month)
        rec["key"] = key
        results[key] = rec
        cache[key]   = rec

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)

        print(f"  ↳ {rec['unique_in_sample']} unique / ~{rec['estimated_total']:,} total")

    return results


def collect_aiml_month(year: int, month: int) -> dict:
    """
    Harvest OAI-PMH for cs.AI ∪ cs.LG ∪ cs.CL ∪ stat.ML papers submitted in
    the target month (identified by YYMM ID prefix).  Deduplicates by paper ID
    so cross-listed papers are counted only once.
    """
    prefix    = yymm(year, month)
    from_date = (date(year, month, 1) - timedelta(days=7)).isoformat()
    next_m    = date(year + (month == 12), month % 12 + 1, 1)
    until_date = (next_m + timedelta(days=14)).isoformat()

    seen: dict[str, str] = {}   # arxiv_id → first_author

    for oai_set in AIML_SETS:
        token = None
        page  = 0
        new_this_set = 0
        while new_this_set < TARGET_AIML:
            try:
                records, token = oai_list_records(from_date, until_date, token, oai_set)
            except Exception as exc:
                print(f"    OAI error ({oai_set}): {exc}")
                break
            page += 1
            for rec in records:
                arxiv_id = record_arxiv_id(rec)
                if arxiv_id and arxiv_id.startswith(f"{prefix}.") and arxiv_id not in seen:
                    author = extract_first_author(rec)
                    if author:
                        seen[arxiv_id] = author
                        new_this_set  += 1
            print(f"    {oai_set} p{page}: +{new_this_set} ({len(seen)} total unique)", flush=True)
            if token is None:
                break

    authors = list(seen.values())
    return {
        "year":             year,
        "month":            month,
        "sample_size":      len(authors),
        "unique_in_sample": len(set(authors)),
        "authors":          authors,
    }


def collect_all_aiml() -> dict:
    cache: dict = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)

    months = []
    y, m = 2025, 5
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    results = {}
    for year, month in months:
        key = f"{year}-{month:02d}-aiml"
        if key in cache:
            r = cache[key]
            print(f"[cache] {key}: {r['unique_in_sample']} unique / {r['sample_size']} sample")
            results[key] = r
            continue

        print(f"[fetch AI/ML] {year}-{month:02d} (prefix {yymm(year,month)})…")
        rec      = collect_aiml_month(year, month)
        rec["key"] = key
        results[key] = rec
        cache[key]   = rec

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)

        print(f"  ↳ {rec['unique_in_sample']} unique / {rec['sample_size']} sample")

    return results


# ── Statistics ───────────────────────────────────────────────────────────────

def mk_test(series):
    """Mann-Kendall via Kendall τ between series and its time index."""
    t  = np.arange(len(series))
    res = stats.kendalltau(t, np.array(series, dtype=float))
    return float(res.statistic), float(res.pvalue)  # type: ignore[union-attr]


def ols(series):
    t   = np.arange(len(series), dtype=float)
    res = stats.linregress(t, np.array(series, dtype=float))
    return float(res.slope), float(res.intercept), float(res.rvalue**2), float(res.pvalue)  # type: ignore[union-attr]


# ── Plotting ─────────────────────────────────────────────────────────────────

BLUE   = "#2a6eb5"
ORANGE = "#d4631a"
RED    = "#c0392b"


def panel(ax, x, values, color, title, ylabel, su):
    ax.bar(x, values, color=color, alpha=0.72, zorder=2)
    trend = su["slope"] * x + su["intercept"]
    ax.plot(x, trend, "--", color=RED, lw=2, zorder=3,
            label=f"OLS  slope={su['slope']:+.1f}/mo  R²={su['r2']:.2f}  p={su['p']:.3f}")
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=6)
    ax.legend(fontsize=8, loc="upper left")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{int(v):,}"))
    ax.grid(axis="y", alpha=0.3, zorder=1)

    mk_txt = (f"Mann-Kendall  τ = {su['mk_tau']:.3f}   p = {su['mk_p']:.3f}")
    ax.text(0.99, 0.96, mk_txt, transform=ax.transAxes,
            fontsize=8, va="top", ha="right",
            color="darkred",
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow",
                      ec="#999", alpha=0.85))


def make_figure(df: pd.DataFrame, su: dict, st: dict):
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    x = np.arange(len(df))

    panel(axes[0], x, df["unique_in_sample"].values, BLUE,
          "Unique first authors per month on arXiv  (sample ≤ 500 new papers/mo)",
          "Unique first authors\n(in sample)", su)

    panel(axes[1], x, df["estimated_total"].values, ORANGE,
          "Estimated total new papers submitted per month",
          "Estimated total papers\n(from max sequence number)", st)

    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["label"].tolist(), rotation=45,
                            ha="right", fontsize=9)

    fig.suptitle("arXiv contributor growth  ·  May 2025 – April 2026\n"
                 "Hypothesis: Gen AI is driving an explosion of new submitters",
                 fontsize=12, y=1.01)
    plt.tight_layout()
    plt.savefig("figure.png", dpi=150, bbox_inches="tight")
    print("Figure saved → figure.png")


# ── README ───────────────────────────────────────────────────────────────────

def write_readme(df: pd.DataFrame, su: dict, st: dict):
    def sig(p):
        return "**significant** (p < 0.05)" if p < 0.05 else "not significant (p ≥ 0.05)"

    trend_u = "increasing" if su["slope"] > 0 else "decreasing"
    trend_t = "increasing" if st["slope"] > 0 else "decreasing"

    rows = "\n".join(
        f"| {row['label']} | {row['estimated_total']:,} | {row['sample_size']} | {row['unique_in_sample']} |"
        for _, row in df.iterrows()
    )

    readme = f"""\
# arXiv contributor growth: is Gen AI causing an explosion of new submitters?

## Hypothesis

With the widespread adoption of generative AI tools and autonomous coding
agents, the barrier to writing and submitting research papers has fallen
significantly. We hypothesize that this has produced a measurable
**explosion of new submitters** on arXiv over the period May 2025 – April 2026.

## Methodology

### Data source

We use the public **arXiv OAI-PMH harvest API**
(`export.arxiv.org/oai2`, metadata prefix `arXiv`).
This interface is designed for bulk metadata retrieval and does not apply the
same rate limits as the search API.

### Identifying new submissions by month

arXiv paper identifiers encode the month of first submission: a paper with
ID `2505.NNNNN` was submitted for the first time in **May 2025**.  For each
target month `YYMM`, we harvest OAI-PMH records within a ±2-week window
around that month and keep only records whose identifier prefix matches
`YYMM.`, giving an unambiguous link between a paper and its submission month
regardless of later revisions.

### Proxy metric for unique submitters

The OAI-PMH arXiv metadata exposes **author names** but not the arXiv account
identity of the submitter.  We use the **first-listed author** as a proxy for
the submitter — a valid approximation because the submitting author is most
often the first or corresponding author.

### Estimating total monthly volume

We record the largest sequence number seen among the collected papers for month
`YYMM` (e.g., `2505.18742`).  Because arXiv assigns sequence numbers
sequentially starting from `00001` within each month, the maximum observed
number provides a lower-bound estimate of total papers submitted that month.

### Sample size

We collect up to **{TARGET_SAMPLE} new papers per month** (first author names
from sampled papers matching the ID prefix). This is enough for robust trend
analysis while keeping runtime reasonable.

### Statistical tests

Two complementary tests are applied to both the unique-author count and the
estimated total submission count:

| Test | Description |
|------|-------------|
| **OLS linear regression** | Regresses the monthly value on time (months 0–11). Reports slope (units/month), R², and two-sided p-value. |
| **Mann-Kendall trend test** | Non-parametric rank-correlation (Kendall τ) between values and time index. Robust to non-Gaussian distributions and small samples. |

Significance threshold: **α = 0.05**.

## Results

### Monthly data

| Month | Est. total papers | Sample size | Unique first authors |
|-------|------------------|-------------|----------------------|
{rows}

### Trend: unique first authors

| Statistic | Value |
|-----------|-------|
| OLS slope | **{su['slope']:+.2f} per month** |
| R² | {su['r2']:.3f} |
| OLS p-value | {su['p']:.4f} — {sig(su['p'])} |
| Mann-Kendall τ | {su['mk_tau']:.3f} |
| Mann-Kendall p | {su['mk_p']:.4f} — {sig(su['mk_p'])} |

The unique-first-author count shows a **{trend_u}** trend
({sig(su['p'])} at α = 0.05).

### Trend: total papers submitted

| Statistic | Value |
|-----------|-------|
| OLS slope | **{st['slope']:+.0f} papers per month** |
| R² | {st['r2']:.3f} |
| OLS p-value | {st['p']:.4f} — {sig(st['p'])} |
| Mann-Kendall τ | {st['mk_tau']:.3f} |
| Mann-Kendall p | {st['mk_p']:.4f} — {sig(st['mk_p'])} |

Total submissions show a **{trend_t}** trend
({sig(st['p'])} at α = 0.05).

### Figure

![arXiv submitter and submission trends, May 2025 – April 2026](figure.png)

## Summary and interpretation

{"### Evidence supports the hypothesis" if su['p'] < 0.05 and su['slope'] > 0 else "### Inconclusive or negative evidence"}

{"The data reveal a **statistically significant upward trend** in unique first authors per month on arXiv (OLS p = " + f"{su['p']:.4f}" + "), consistent with a genuine expansion of the contributor base.  Combined with the growing total submission volume (OLS p = " + f"{st['p']:.4f}" + "), this supports the hypothesis that Gen AI tools are lowering the barrier to research submission and attracting new contributors to arXiv." if su['p'] < 0.05 and su['slope'] > 0 else "Within this 12-month window the trend in unique first authors is **not statistically significant** at α = 0.05.  This does not definitively refute the hypothesis — 12 months may be too short a window to separate a structural shift from seasonal variation, and any effect may be concentrated in specific sub-fields (e.g., cs.AI, cs.CL) rather than arXiv as a whole."}

### Caveats and limitations

1. **No historical baseline** — this study covers only 12 months.  Without a
   multi-year baseline (e.g., 2020–2024) it is impossible to determine whether
   the observed trend is anomalous or simply part of arXiv's long-run secular
   growth.

2. **Name disambiguation** — first-author names are not disambiguated.  The
   same person may appear under different name variants (initials vs. full
   name, transliteration differences), slightly inflating the unique count;
   conversely, common names may collapse distinct individuals, deflating it.

3. **First author ≠ submitter** — the OAI-PMH API does not expose the arXiv
   account that submitted the paper.  Advisors, lab coordinators, or
   co-authors sometimes submit on behalf of first authors.

4. **Sampling bias** — we collect the first {TARGET_SAMPLE} papers matching
   each month's ID prefix in OAI-PMH order, which is sorted by datestamp of
   the most recent version.  This over-samples papers revised soon after
   submission relative to those revised later.

5. **AI-generated papers vs. new authors** — even if unique-author counts
   grow, this could reflect a small group of existing researchers producing
   more papers per person (AI-assisted productivity) rather than genuinely
   new contributors entering the platform.

6. **Total-papers estimate** — the maximum sequence number gives a lower bound
   on monthly volume (we only see the largest ID in our sample, not the true
   maximum for the month).

## Reproducibility

```bash
pip install requests pandas matplotlib scipy numpy
python main.py
```

Data is cached in `data_cache.json` after the first run; subsequent runs
load from cache and re-generate the figure and README.
"""

    with open("README.md", "w") as f:
        f.write(readme)
    print("README.md written.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    collect_all()       # populates YYMM keys in data_cache.json
    collect_all_aiml()  # populates YYMM-aiml keys in data_cache.json
    print("\nAll data collected.  Run analyze.py to generate figure and README.")


if __name__ == "__main__":
    main()
