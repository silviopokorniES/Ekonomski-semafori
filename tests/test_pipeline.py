"""Tests for pipeline.run_indicator on the R fixtures (task 2.2; the full parity
sweep is test_parity.py, task 2.3)."""

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from ekonomski_semafori.config import load_countries, load_indicators, load_settings
from ekonomski_semafori.pipeline import SkippedIndicator, run_indicator

R_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}


def r_output(folder, country_dir: str, name_hr: str) -> pd.DataFrame:
    """One indicator's rows of the combined R Excel output, with ISO dates."""
    files = list((folder / country_dir).glob("combined_*.xlsx")) + list((folder / country_dir).glob("Business_Cycle_*.xlsx"))
    frame = pd.read_excel(files[0], sheet_name=0 if "combined" in files[0].name else "6_svi_indikatori")
    frame = frame[frame["Varijabla"] == name_hr].copy()
    frame["time"] = pd.to_datetime([f"{R_MONTHS[s.split()[0]]:02d}-{s.split()[1]}" for s in frame["time"]], format="%m-%Y")
    return frame.rename(columns={"Mjesečna promjena (%)": "mom_z", "Odstupanje od trenda (%)": "cycle_z"}).set_index("time")


def test_run_indicator_reproduces_r_for_industrial_production(r_fixtures) -> None:
    folder, _ = r_fixtures
    raw_file = next((folder / "HR").glob("*get_eurostat_sts_inpr_m_M-HR-*.csv"))
    raw = pd.read_csv(raw_file)
    series = pd.Series(raw["values"].to_numpy(float), index=pd.DatetimeIndex(pd.to_datetime(raw["time"])))
    countries, indicators = load_countries(), load_indicators()
    indicator = {i.id: i for i in indicators}["industrial_production"]
    settings = replace(load_settings(), trend_method="hp_on_d12")
    out = run_indicator(countries["HR"], indicator, settings, history_start=date(2015, 1, 1), raw=series).set_index("time")
    expected = r_output(folder, "r_output_HR", indicator.name_hr)
    assert out.index[0] == expected.index[0] and out.index[-1] == expected.index[-1]
    joined = out.join(expected, lsuffix="_py", rsuffix="_r")
    for col in ("mom_z", "cycle_z"):
        gap = float(np.max(np.abs(joined[f"{col}_py"] - joined[f"{col}_r"])))
        assert gap < 1e-4, f"{col}: max abs gap {gap:.2e}"


def test_run_indicator_skips_short_series() -> None:
    countries, indicators, settings = load_countries(), load_indicators(), load_settings()
    indicator = {i.id: i for i in indicators}["industrial_production"]
    short = pd.Series(np.linspace(100, 110, 12), index=pd.date_range("2024-01-01", periods=12, freq="MS"))
    with pytest.raises(SkippedIndicator):
        run_indicator(countries["HR"], indicator, settings, raw=short)
