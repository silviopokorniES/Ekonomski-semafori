"""Tests for output.py on a small synthetic panel (task 2.4)."""

from pathlib import Path

import numpy as np
import pandas as pd

from ekonomski_semafori.config import load_countries, load_indicators, load_settings
from ekonomski_semafori.output import CATEGORY_SHEETS, MASTER_COLUMNS, build_long, write_all


def _panel() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    frames = []
    for country in ("HR", "AT"):
        for indicator_id in ("gdp", "building_permits", "unemployment"):
            time = pd.date_range("2014-11-01", periods=6, freq="MS")
            frames.append(pd.DataFrame({"country": country, "indicator_id": indicator_id, "time": time,
                                        "mom_z": rng.normal(size=6), "cycle_z": rng.normal(size=6)}))
    return pd.concat(frames, ignore_index=True)


def test_build_long_expands_categories_and_starts_at_output_start() -> None:
    long = build_long(_panel(), load_countries(), load_indicators(), load_settings())
    assert list(long.columns) == MASTER_COLUMNS
    assert long["time"].min() == pd.Timestamp("2015-02-01")
    gdp = long[(long["country"] == "HR") & (long["indicator_id"] == "gdp")]
    assert sorted(gdp["category"].unique()) == ["demand", "supply"]
    assert len(gdp) == 2 * 3
    assert long.loc[long["time"] == "2015-02-01", "label"].iloc[0] == "veljača 2015"
    assert (long.loc[long["indicator_id"] == "building_permits", "indicator_name_hr"] == "Građevinske dozvole").all()


def test_written_files_round_trip(tmp_path: Path) -> None:
    countries, indicators, settings = load_countries(), load_indicators(), load_settings()
    long = write_all(_panel(), countries, indicators, settings, tmp_path)
    master = pd.read_csv(tmp_path / "all_countries_long.csv", parse_dates=["time"])
    assert (tmp_path / "all_countries_long.csv").read_bytes()[:3] == b"\xef\xbb\xbf"
    pd.testing.assert_frame_equal(master, long, check_dtype=False)
    for path in (tmp_path / "by_indicator").glob("*.csv"):
        view = pd.read_csv(path, parse_dates=["time"])
        pd.testing.assert_frame_equal(view, long[long["indicator_id"] == path.stem].reset_index(drop=True), check_dtype=False)
    bounds = pd.read_csv(tmp_path / "axis_bounds.csv")
    assert {"country", "all", "indicator"} == set(bounds["scope_type"])
    assert bounds.loc[(bounds["scope"] == "ALL") & (bounds["category"] == "ALL"), "cycle_min"].iloc[0] == round(long["cycle_z"].min(), 3)
    legacy = tmp_path / "legacy"
    assert (legacy / "combined_standardized_MoM_and_Cycle_Croatia.xlsx").exists()
    workbook = pd.ExcelFile(legacy / "Business_Cycle_Austria.xlsx")
    assert workbook.sheet_names[-1] == "6_svi_indikatori"
    assert set(workbook.sheet_names[:-1]) <= set(CATEGORY_SHEETS.values())
    sheet = workbook.parse("6_svi_indikatori")
    assert list(sheet.columns) == ["time", "Mjesečna promjena (%)", "Odstupanje od trenda (%)", "Varijabla"]
    assert sheet["time"].iloc[0] == "February 2015"
