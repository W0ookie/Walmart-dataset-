from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

REQUIRED_FILES = {
    "stores": "STORE_STATUS_PUBLIC_VIEW_3007829193429392206.csv",
    "retail_sales": "RSXFS.csv",
    "weekly_sales": "Walmart_sales.csv",
    "sams_sales": "sams_club_net_sales_1991_current.csv",
    "walmart_us_sales": "walmart_us_net_sales_1991_current.csv",
    "population": "NST-EST2025-ALLDATA.csv",
}

STATE_ABBREV = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}


def _path(key: str) -> Path:
    filename = REQUIRED_FILES[key]
    for folder in (DATA_DIR, ROOT):
        path = folder / filename
        if path.exists():
            return path
    raise FileNotFoundError(f"Missing data file: {filename}")


def load_store_locations() -> pd.DataFrame:
    stores_raw = pd.read_csv(_path("stores"))
    columns = [
        "businessUnit_name",
        "businessUnit_number",
        "Description",
        "Type",
        "Address",
        "City",
        "County",
        "State",
        "Postal Code",
        "Operation Status",
        "x",
        "y",
    ]
    stores = stores_raw[columns].copy()
    stores["State"] = stores["State"].astype(str).str.strip().str.upper()
    stores["Type"] = stores["Type"].astype(str).str.strip()
    stores["x"] = pd.to_numeric(stores["x"], errors="coerce")
    stores["y"] = pd.to_numeric(stores["y"], errors="coerce")

    earth_radius = 6378137
    stores["longitude"] = stores["x"] / earth_radius * 180 / math.pi
    stores["latitude"] = (
        2 * stores["y"].apply(lambda value: math.atan(math.exp(value / earth_radius)))
        - math.pi / 2
    ) * 180 / math.pi

    stores = stores.dropna(subset=["State", "longitude", "latitude"]).copy()
    stores = stores[
        stores["latitude"].between(17, 72)
        & stores["longitude"].between(-180, -60)
    ].copy()
    stores["is_open"] = stores["Operation Status"].str.lower().eq("open")
    return stores


def load_population() -> pd.DataFrame:
    population_raw = pd.read_csv(_path("population"))
    population = (
        population_raw[population_raw["SUMLEV"] == 40][["NAME", "POPESTIMATE2025"]]
        .rename(columns={"NAME": "state", "POPESTIMATE2025": "population_2025"})
        .copy()
    )
    population["State"] = population["state"].map(STATE_ABBREV)
    return population.dropna(subset=["State"])


def build_state_summary(stores: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    counts = (
        stores.groupby("State", as_index=False)
        .agg(
            walmart_store_count=("businessUnit_number", "size"),
            open_locations=("is_open", "sum"),
        )
    )
    summary = counts.merge(population, on="State", how="left")
    summary["stores_per_100k"] = (
        summary["walmart_store_count"] / summary["population_2025"] * 100_000
    )
    return summary.dropna(subset=["population_2025"]).sort_values(
        "walmart_store_count", ascending=False
    )


def load_retail_sales() -> pd.DataFrame:
    retail_sales = pd.read_csv(_path("retail_sales"))
    retail_sales = retail_sales.rename(
        columns={"observation_date": "date", "RSXFS": "retail_sales"}
    )
    retail_sales["date"] = pd.to_datetime(retail_sales["date"])
    retail_sales["retail_sales"] = pd.to_numeric(
        retail_sales["retail_sales"], errors="coerce"
    )
    return retail_sales.dropna().sort_values("date")


def load_weekly_sales() -> pd.DataFrame:
    weekly = pd.read_csv(_path("weekly_sales"))
    weekly["Date"] = pd.to_datetime(weekly["Date"], dayfirst=True, errors="coerce")
    numeric_columns = [
        "Weekly_Sales",
        "Holiday_Flag",
        "Temperature",
        "Fuel_Price",
        "CPI",
        "Unemployment",
    ]
    for column in numeric_columns:
        weekly[column] = pd.to_numeric(weekly[column], errors="coerce")
    return weekly.dropna(subset=["Date", "Weekly_Sales"]).sort_values("Date")


def load_segment_sales() -> pd.DataFrame:
    sams_sales = pd.read_csv(_path("sams_sales"))
    walmart_us_sales = pd.read_csv(_path("walmart_us_sales"))
    segment_sales = pd.concat([sams_sales, walmart_us_sales], ignore_index=True)
    segment_sales["net_sales_billions_usd"] = pd.to_numeric(
        segment_sales["net_sales_billions_usd"], errors="coerce"
    )
    segment_sales["yoy_change_percent"] = pd.to_numeric(
        segment_sales["yoy_change_percent"], errors="coerce"
    )
    segment_sales = segment_sales.dropna(subset=["net_sales_billions_usd"]).copy()
    segment_sales["fiscal_year_end_year"] = segment_sales[
        "fiscal_year_end_year"
    ].astype(int)
    return segment_sales.sort_values(["segment", "fiscal_year_end_year"])
