"""Helpers for the R parity check (task 2.3): rebuild each (country, indicator) input
from the raw fixture files and read the R output for it.

The raw Eurostat fixtures are the frames get_eurostat returned in R (one file per
request, sometimes holding two series); rows are selected by the indicator's
filters. The ECB fixture is the get_data frame (obstime, obsvalue). Local Excel
inputs are read from data/ (the same files the R run used)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ekonomski_semafori.config import Country, Indicator
from ekonomski_semafori.fetch import fetch_local

R_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}


def raw_series(folder: Path, index: pd.DataFrame, country: Country, indicator: Indicator) -> pd.Series:
    """The raw input series for the pair, rebuilt from the fixture files."""
    rows = index[index["country"] == country.code]
    if indicator.source == "eurostat":
        tag_prefix = f"{indicator.dataset}_"
        match = rows[(rows["fun"] == "get_eurostat") & rows["tag"].str.startswith(tag_prefix)]
        frame = pd.read_csv(_file(folder, country.code, int(match["seq"].iloc[0])))
        for key, value in indicator.filters.items():
            if key in frame.columns:
                frame = frame[frame[key].astype(str) == value]
        return pd.Series(frame["values"].to_numpy(float), index=pd.DatetimeIndex(pd.to_datetime(frame["time"])), name=indicator.id)
    if indicator.source == "ecb":
        match = rows[rows["fun"] == "get_data"]
        frame = pd.read_csv(_file(folder, country.code, int(match["seq"].iloc[0])))
        time = pd.PeriodIndex(frame["obstime"].astype(str), freq="Q").to_timestamp(how="start")
        return pd.Series(frame["obsvalue"].to_numpy(float), index=time, name=indicator.id)
    frame = fetch_local(indicator.path, indicator.column)
    return pd.Series(frame["value"].to_numpy(), index=pd.DatetimeIndex(frame["time"]), name=indicator.id)


def _file(folder: Path, country: str, seq: int) -> Path:
    return next((folder / country).glob(f"{seq:04d}_*.csv"))


def r_output(folder: Path, country: Country) -> pd.DataFrame:
    """The combined R output for a country: [time, name_hr, mom_z, cycle_z]."""
    if country.code == "HR":
        frame = pd.read_excel(folder / "r_output_HR" / "combined_standardized_MoM_and_Cycle_Croatia.xlsx")
    else:
        name = country.name_en.replace(" ", "_")
        frame = pd.read_excel(folder / "r_output" / f"Business_Cycle_{name}.xlsx", sheet_name="6_svi_indikatori")
    frame["time"] = pd.to_datetime([f"{R_MONTHS[s.split()[0]]:02d}-{s.split()[1]}" for s in frame["time"]], format="%m-%Y")
    return frame.rename(columns={"Mjesečna promjena (%)": "mom_z", "Odstupanje od trenda (%)": "cycle_z", "Varijabla": "name_hr"})[["time", "name_hr", "mom_z", "cycle_z"]]
