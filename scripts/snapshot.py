# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pandas==2.3.2",
#     "pyarrow>=17",
#     "requests>=2.31",
# ]
# ///
"""Download the OECD GHG emissions dataset from the OECD SDMX API.

Writes `public/ghg.parquet`, which the app loads at startup. Run this only when
you want fresh data:

    uv run scripts/snapshot.py

or with plain pip:

    pip install requests pandas pyarrow
    python scripts/snapshot.py

Dataflow: OECD.CFE.EDS:DSD_REG_CLIM@DF_GHG(2.4) - "Greenhouse gas emissions -
Regions". Dimensions, in order:

    FREQ . TERRITORIAL_LEVEL . REF_AREA . TERRITORIAL_TYPE . MEASURE
         . RET_PERIOD . HEAT_STRESS . PROJ_SCENARIO . POLLUTANT_CONCENTRATION
         . UNIT_MEASURE

`format=csvfilewithlabels` is used because the app's dropdowns display human
readable labels ("United States", "GHG emissions from agriculture") rather than
SDMX codes ("USA", "GHG_AGRICULTURE"). Note that in that format every dimension
gets a code column and a label column, but `TIME_PERIOD` and `OBS_VALUE` have no
labels, so their label columns are empty - read the code columns for those two.
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://sdmx.oecd.org/public/rest/data"
AGENCY = "OECD.CFE.EDS"
DATAFLOW = "DSD_REG_CLIM@DF_GHG"
VERSION = "2.4"

# 3-character ISO codes for every country in the dataset.
COUNTRIES = [
    "ARG", "AUS", "AUT", "BEL", "BGR", "BRA", "CAN", "CHE", "CHL", "CHN", "COL",
    "CRI", "CZE", "DEU", "DNK", "ESP", "EST", "FIN", "FRA", "GBR", "GRC", "HRV",
    "HUN", "IDN", "IND", "IRL", "ISL", "ISR", "ITA", "JPN", "KOR", "LTU", "LUX",
    "LVA", "MEX", "MLT", "NLD", "NOR", "NZL", "PER", "POL", "PRT", "ROU", "RUS",
    "SVK", "SVN", "SWE", "TUN", "TUR", "USA", "ZAF",
]

MEASURES = [
    "GHG_AGRICULTURE",
    "GHG_BUILDINGS",
    "GHG_CTRY_TOTAL",
    "GHG_DOM_AVIATION",
    "GHG_DOM_SHIPPING",
    "GHG_INDUSTRY",
    "GHG_MANUFACT",
    "GHG_POWER",
    "GHG_REG_TOTAL",
    "GHG_ROAD_TRANSPORT",
    "GHG_TRANSPORT",
    "GHG_WASTE",
]

UNITS = ["T_CO2E", "T_CO2E_PS"]

MIN_YEAR = 1990

REQUEST_TIMEOUT = 300  # seconds
MAX_ATTEMPTS = 4

OUTPUT = Path(__file__).resolve().parent.parent / "public" / "ghg.parquet"


def build_key() -> str:
    """Build the SDMX series key for all countries, measures and units."""
    return ".".join(
        [
            "A",  # FREQ: annual
            "CTRY",  # TERRITORIAL_LEVEL
            "+".join(COUNTRIES),  # REF_AREA
            "_Z",  # TERRITORIAL_TYPE
            "+".join(MEASURES),  # MEASURE
            "_Z",  # RET_PERIOD
            "_Z",  # HEAT_STRESS
            "_Z",  # PROJ_SCENARIO
            "_Z",  # POLLUTANT_CONCENTRATION
            "+".join(UNITS),  # UNIT_MEASURE
        ]
    )


def fetch_csv() -> str:
    """Download the dataset as SDMX CSV with labels, retrying on network errors."""
    url = f"{BASE_URL}/{AGENCY},{DATAFLOW},{VERSION}/{build_key()}"
    params = {"startPeriod": MIN_YEAR, "format": "csvfilewithlabels"}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        started = time.time()
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - any network failure is retryable
            wait = 2**attempt
            print(
                f"attempt {attempt}/{MAX_ATTEMPTS} failed after "
                f"{time.time() - started:.0f}s ({type(exc).__name__}); retrying in {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue

        size_mb = len(response.content) / 1024 / 1024
        print(f"downloaded {size_mb:.1f} MB in {time.time() - started:.1f}s")
        return response.text

    raise RuntimeError(f"Could not download the dataset after {MAX_ATTEMPTS} attempts")


def build_dataframe() -> pd.DataFrame:
    """Parse the SDMX CSV into the app's tidy dataframe."""
    raw = pd.read_csv(io.StringIO(fetch_csv()), low_memory=False)

    df = pd.DataFrame(
        {
            "Year": raw["TIME_PERIOD"],
            "Value": raw["OBS_VALUE"],
            "Country": raw["Reference area"],
            "Measure": raw["Measure"],
            "Unit of measure": raw["Unit of measure"],
        }
    )

    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Value", "Year"])
    df = df[df["Year"] >= MIN_YEAR]
    df["Year"] = df["Year"].astype(int).astype(str)

    # Sorted output keeps the Parquet file byte-stable between runs.
    df = df.sort_values(["Country", "Measure", "Unit of measure", "Year"])
    return df.reset_index(drop=True)


def main() -> int:
    df = build_dataframe()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT, index=False, compression="zstd")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {len(df):,} rows to {OUTPUT}")
    print(f"Size: {size_kb:.1f} KB")
    print(f"Years: {df['Year'].min()}-{df['Year'].max()}")
    print(f"Countries: {df['Country'].nunique()}  Measures: {df['Measure'].nunique()}")
    print(f"Units: {sorted(df['Unit of measure'].unique())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
