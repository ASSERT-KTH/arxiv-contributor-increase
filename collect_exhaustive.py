#!/usr/bin/env python3
"""
Exhaustive per-category collection for cs.SE and cs.LG.

Rationale: sparse sampling inflates uniqueness ratios artificially because
most submitters publish exactly one paper per month.  In a small sample,
the chance of seeing the same author twice is negligible regardless of the
true repeat rate.  Exhaustive collection gives the true unique-submitter
count.

Strategy:
  For each (year, month, oai_set):
    - Query OAI-PMH starting from the 1st of the month (tight window to
      maximise new-month density per page).
    - Keep only records whose arXiv ID starts with YYMM. (unambiguous
      new submission flag).
    - Follow ALL resumption tokens until we see two consecutive pages
      with zero matching records (meaning we've passed the month's block
      in the feed).
    - Store the complete list of first-author names.

Caches results in data_cache.json under the key  "YYYY-MM-<cat>"
(e.g. "2025-05-cs.LG").
"""

import requests
import xml.etree.ElementTree as ET
import time
import json
import os
from datetime import date, timedelta

CACHE_FILE   = "data_cache.json"
OAI_URL      = "https://export.arxiv.org/oai2"
REQUEST_WAIT = 4.0
HEADERS      = {"User-Agent": "arxiv-submitter-study/1.0 (martin2020+claude@monperrus.net)"}

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
ARX_NS = "http://arxiv.org/OAI/arXiv/"

CATEGORIES = {
    "cs.LG": "cs:cs:LG",
    "cs.SE": "cs:cs:SE",
}


def yymm(year: int, month: int) -> str:
    return f"{year % 100:02d}{month:02d}"


def oai_page(from_date: str, until_date: str,
             oai_set: str, token: str | None = None):
    if token:
        params = {"verb": "ListRecords", "resumptionToken": token}
    else:
        params = {"verb": "ListRecords", "from": from_date, "until": until_date,
                  "metadataPrefix": "arXiv", "set": oai_set}
    time.sleep(REQUEST_WAIT)
    resp = requests.get(OAI_URL, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    root    = ET.fromstring(resp.text)
    records = root.findall(f".//{{{OAI_NS}}}record")
    tok_el  = root.find(f".//{{{OAI_NS}}}resumptionToken")
    next_tok = tok_el.text if (tok_el is not None and tok_el.text) else None
    return records, next_tok


def extract_first_author(record) -> str | None:
    meta      = record.find(f".//{{{ARX_NS}}}arXiv")
    if meta is None:
        return None
    keynames  = meta.findall(f".//{{{ARX_NS}}}keyname")
    forenames = meta.findall(f".//{{{ARX_NS}}}forenames")
    if not keynames:
        return None
    kn = (keynames[0].text  or "").strip()
    fn = (forenames[0].text if forenames else "").strip()
    return f"{kn}, {fn}" if fn else kn


def record_id(record) -> str | None:
    el = record.find(f"{{{OAI_NS}}}header/{{{OAI_NS}}}identifier")
    return el.text.split(":")[-1] if el is not None and el.text else None


def collect_month(year: int, month: int, oai_set: str, cat_label: str) -> dict:
    prefix     = yymm(year, month)
    # Start exactly at month boundary — maximises new-month density per page.
    from_date  = date(year, month, 1).isoformat()
    next_m     = date(year + (month == 12), month % 12 + 1, 1)
    until_date = (next_m + timedelta(days=14)).isoformat()

    seen: dict[str, str] = {}   # arxiv_id → first_author
    token      = None
    page       = 0
    empty_runs = 0              # consecutive pages with 0 matching records

    while True:
        try:
            records, token = oai_page(from_date, until_date, oai_set, token)
        except Exception as exc:
            print(f"    OAI error p{page+1}: {exc}")
            break

        page += 1
        new_this_page = 0
        for rec in records:
            arxiv_id = record_id(rec)
            if arxiv_id and arxiv_id.startswith(f"{prefix}.") and arxiv_id not in seen:
                author = extract_first_author(rec)
                if author:
                    seen[arxiv_id] = author
                    new_this_page += 1

        print(f"    p{page:02d}: +{new_this_page:4d} new  ({len(seen):5d} total)  "
              f"token={'yes' if token else 'end'}", flush=True)

        if new_this_page == 0:
            empty_runs += 1
            if empty_runs >= 2 or token is None:
                # Two empty pages in a row (or feed exhausted) → done
                break
        else:
            empty_runs = 0

        if token is None:
            break

    authors = list(seen.values())
    return {
        "year":             year,
        "month":            month,
        "category":         cat_label,
        "oai_set":          oai_set,
        "total_papers":     len(seen),       # exhaustive count for this category
        "unique_authors":   len(set(authors)),
        "authors":          authors,
    }


def collect_all():
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

    for cat_label, oai_set in CATEGORIES.items():
        print(f"\n{'='*60}")
        print(f"Category: {cat_label}  ({oai_set})")
        print(f"{'='*60}")

        for year, month in months:
            key = f"{year}-{month:02d}-{cat_label}"
            if key in cache:
                r = cache[key]
                print(f"[cache] {key}: {r['unique_authors']} unique / "
                      f"{r['total_papers']} total")
                continue

            print(f"[fetch] {key}  (prefix {yymm(year,month)})…")
            rec = collect_month(year, month, oai_set, cat_label)
            cache[key] = rec
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)
            print(f"  ↳ {rec['unique_authors']} unique / {rec['total_papers']} total papers")


if __name__ == "__main__":
    collect_all()
