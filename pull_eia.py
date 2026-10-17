"""Pull hourly fuel mix and demand for one balancing authority from the EIA API v2.

Usage (from the repo root, with the venv active):
    python pull_eia.py PJM 2025
    python pull_eia.py CISO 2025

Saves two parquet files to data/raw/. Needs EIA_API_KEY in .env.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

BASE = "https://api.eia.gov/v2/electricity/rto"
PAGE = 5000  # the API returns at most 5,000 rows per request


def fetch(route, respondent, start, end, key, extra=None, tiebreak=None, page=PAGE, get=requests.get):
    """Page through one EIA route and return every row as a DataFrame."""
    params = {
        "api_key": key,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": respondent,
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": page,
    }
    if tiebreak:  # several rows share one hour, so add a stable second sort key
        params["sort[1][column]"] = tiebreak
        params["sort[1][direction]"] = "asc"
    params.update(extra or {})

    rows, offset, total = [], 0, None
    while total is None or offset < total:
        params["offset"] = offset
        r = get(f"{BASE}/{route}/data/", params=params, timeout=60)
        r.raise_for_status()
        resp = r.json()["response"]
        total = int(resp["total"])
        batch = resp["data"]
        if not batch:
            break
        rows.extend(batch)
        offset += page
    if len(rows) != total:
        raise RuntimeError(f"{route}: expected {total} rows, got {len(rows)}")
    return pd.DataFrame(rows)


def fuel_mix_wide(df):
    """One row per UTC hour, one column per fuel code, values in MWh."""
    df = df.copy()
    df["period"] = pd.to_datetime(df["period"], utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    dups = int(df.duplicated(["period", "fueltype"]).sum())
    wide = df.pivot_table(index="period", columns="fueltype", values="value", aggfunc="first")
    return wide.sort_index(), dups


def demand_series(df):
    df = df.copy()
    df["period"] = pd.to_datetime(df["period"], utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.drop_duplicates("period").set_index("period")["value"].sort_index().rename("demand_mw")


def missing_hours(index, start, end):
    expected = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"), freq="h")
    return expected.difference(index)


def main(respondent, year, out="data/raw"):
    load_dotenv()
    key = os.getenv("EIA_API_KEY")
    if not key:
        sys.exit("EIA_API_KEY not found. Put it in a .env file in the repo root.")

    start, end = f"{year}-01-01T00", f"{year}-12-31T23"
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    raw_fuel = fetch("fuel-type-data", respondent, start, end, key, tiebreak="fueltype")
    mix, dups = fuel_mix_wide(raw_fuel)
    raw_dem = fetch("region-data", respondent, start, end, key, extra={"facets[type][]": "D"})
    dem = demand_series(raw_dem)

    tag = respondent.lower()
    mix.to_parquet(out / f"{tag}_fuel_mix_{year}.parquet")
    dem.to_frame().to_parquet(out / f"{tag}_demand_{year}.parquet")

    print(f"{respondent} {year}")
    print(f"  fuel mix: {len(raw_fuel)} rows -> {mix.shape[0]} hours x {mix.shape[1]} fuels; duplicates: {dups}")
    print(f"  fuel codes: {list(mix.columns)}")
    print(f"  demand:   {len(dem)} hours")
    for name, idx in (("fuel mix", mix.index), ("demand", dem.index)):
        gaps = missing_hours(idx, start, end)
        print(f"  {name} missing hours: {len(gaps)}", list(gaps[:5]) if len(gaps) else "")
    print(mix.head())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python pull_eia.py <PJM|CISO> <year>")
    main(sys.argv[1].upper(), int(sys.argv[2]))