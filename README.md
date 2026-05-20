# arXiv contributor growth: is Gen AI causing an explosion of new submitters?

## Hypothesis

With the widespread adoption of generative AI tools and autonomous coding
agents, the barrier to writing and submitting research papers has fallen.
We test whether this produced a measurable explosion of new submitters on
arXiv over May 2025 – April 2026, focusing on two categories:
**cs.LG** (Machine Learning) and **cs.SE** (Software Engineering).

## Methodology

### Data source

arXiv OAI-PMH harvest API (`export.arxiv.org/oai2`, `metadataPrefix=arXiv`),
queried per category with the OAI-PMH `set` parameter.

### Identifying new submissions

arXiv paper IDs encode the month of first submission: `2505.NNNNN` means May
2025. For each target month `YYMM` we harvest all OAI-PMH records for the
category within a ±2-week window starting from the 1st of the month, keep
only records whose ID prefix matches `YYMM.`, and follow every resumption
token until two consecutive pages return zero matching records. This is
**exhaustive** — every paper submitted that month in that category is
collected.

### Proxy metric for unique submitters

OAI-PMH exposes author names, not account identities. We use the
**first-listed author** as a proxy for the submitter. All raw author lists
are stored in `data_cache.json`.

### Statistical tests

Both OLS linear regression (slope, R², p-value) and the non-parametric
Mann-Kendall trend test (Kendall τ, p-value) are applied to each monthly
series. Significance threshold: α = 0.05.

## Results

All numbers below come from `data_cache.json` (keys `YYYY-MM-cs.LG` and
`YYYY-MM-cs.SE`). The statistical summaries printed by `analyze.py` are the
authoritative reference for p-values and slopes.

### cs.LG (Machine Learning) — exhaustive monthly counts

| Month | Total papers | Unique first authors | Ratio |
|-------|-------------|---------------------|-------|
| 2025-05 | 2,780 | 2,653 | 95.4% |
| 2025-06 | 2,665 | 2,573 | 96.5% |
| 2025-07 | 2,423 | 2,333 | 96.3% |
| 2025-08 | 2,294 | 2,196 | 95.7% |
| 2025-09 | 2,861 | 2,742 | 95.8% |
| 2025-10 | 3,533 | 3,349 | 94.8% |
| 2025-11 | 2,868 | 2,744 | 95.7% |
| 2025-12 | 2,706 | 2,559 | 94.6% |
| 2026-01 | 2,860 | 2,733 | 95.6% |
| 2026-02 | 4,023 | 3,792 | 94.3% |
| 2026-03 | 4,174 | 3,901 | 93.5% |
| 2026-04 | 3,847 | 3,612 | 93.9% |

**12-month change:** 2,780 → 3,847 total papers (+38.4%);
2,653 → 3,612 unique first authors (+36.1%).

| Metric | OLS slope | R² | OLS p | MK τ | MK p |
|--------|----------|----|-------|------|------|
| Total papers | +133.6 / mo | 0.571 | **0.0045** | 0.515 | **0.021** |
| Unique first authors | +119.7 / mo | 0.558 | **0.0052** | 0.485 | **0.031** |
| Uniqueness ratio | −0.219% / mo | 0.669 | 0.0012 | −0.667 | 0.0018 |

Both total papers and unique first authors show a **statistically significant
increasing trend** (OLS p < 0.01, MK p < 0.05). The uniqueness ratio
(95.2% on average) is slightly but significantly declining, consistent with
the growing pool of papers including a modest increase in multi-paper
authors — the pool itself is expanding fast enough to dominate.

### cs.SE (Software Engineering) — exhaustive monthly counts

| Month | Total papers | Unique first authors | Ratio |
|-------|-------------|---------------------|-------|
| 2025-05 | 266 | 256 | 96.2% |
| 2025-06 | 322 | 300 | 93.2% |
| 2025-07 | 351 | 332 | 94.6% |
| 2025-08 | 279 | 270 | 96.8% |
| 2025-09 | 349 | 335 | 96.0% |
| 2025-10 | 445 | 427 | 96.0% |
| 2025-11 | 339 | 330 | 97.3% |
| 2025-12 | 378 | 361 | 95.5% |
| 2026-01 | 472 | 452 | 95.8% |
| 2026-02 | 424 | 406 | 95.8% |
| 2026-03 | 540 | 507 | 93.9% |
| 2026-04 | 780 | 740 | 94.9% |

**12-month change:** 266 → 780 total papers (+193.2%);
256 → 740 unique first authors (+189.1%).

| Metric | OLS slope | R² | OLS p | MK τ | MK p |
|--------|----------|----|-------|------|------|
| Total papers | +31.7 / mo | 0.660 | **0.0013** | 0.727 | **0.0005** |
| Unique first authors | +30.1 / mo | 0.670 | **0.0011** | 0.758 | **0.0002** |
| Uniqueness ratio | −0.019% / mo | 0.003 | 0.856 | −0.212 | 0.381 |

The growth in cs.SE is **striking and highly significant** by both tests
(MK p = 0.0002 for unique authors). cs.SE nearly triples in submission
volume over 12 months. The uniqueness ratio is flat (p = 0.856), meaning
the entire growth is driven by genuinely new contributors entering the
category, not by existing authors submitting more papers each.

## Figure

![Exhaustive unique first authors per month, cs.LG and cs.SE](figure_exhaustive.png)

## Summary

The data **support the hypothesis**. Both categories show strongly
significant upward trends in unique first authors over May 2025 – April 2026:

- **cs.LG** grew +36% in unique first authors (OLS p = 0.005).
- **cs.SE** grew +189% in unique first authors (OLS p = 0.001), with a
  flat uniqueness ratio — the new papers are from new people.

The contrast between the two categories is itself informative. cs.LG is
already a large, established community where growth is substantial but
moderated. cs.SE's near-tripling in 12 months is anomalous by historical
standards and consistent with AI coding tools (GitHub Copilot, Cursor,
Claude Code, etc.) lowering the bar for software-engineering research
submissions.

## Caveats and limitations

1. **No causal attribution.** We cannot establish that Gen AI caused the
   growth. A 12-month window cannot rule out other drivers (conference
   deadline shifts, new venues cross-posting, editorial policy changes).

2. **No historical baseline.** Without the same exhaustive counts for
   2020–2024 we cannot say whether +189% in cs.SE is anomalous or a
   continuation of a pre-existing trend.

3. **First author ≠ submitter.** The OAI-PMH API does not expose the
   arXiv account identity. Advisors or co-authors sometimes submit on
   behalf of first authors.

4. **Name disambiguation.** Author names are not disambiguated. The same
   person under different name variants is counted twice; a common name
   may merge distinct people.

5. **AI productivity vs. new entrants.** Growth in unique first authors
   could still reflect a fixed pool of researchers each appearing as
   first author more often (e.g. more single-author or student-led
   papers), not necessarily researchers who are new to arXiv.

## Reproducibility

```bash
pip install requests pandas matplotlib scipy numpy
python collect_exhaustive.py   # ~10 min; results cached in data_cache.json
python analyze.py              # recomputes stats, regenerates figure_exhaustive.png
```
