"""Tests for output.py on a small synthetic panel (task 2.4)."""

from pathlib import Path

import numpy as np
import pandas as pd

from ekonomski_semafori.config import load_countries, load_indicators, load_settings
from ekonomski_semafori.output import CHART_COLUMNS, MASTER_COLUMNS, build_long, write_all


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
    assert long["clipped"].dtype == bool and long["cycle_z"].abs().max() <= 3
    assert set(long.loc[long["indicator_id"] == "unemployment", "panel"]) == {"confirmation"} and set(long.loc[long["indicator_id"] == "gdp", "panel"]) == {"main"}
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
    gdp = pd.read_csv(tmp_path / "by_indicator" / "gdp.csv")
    assert list(gdp.columns) == CHART_COLUMNS + ["Skupina"]
    assert not gdp.duplicated(["Datum", "Varijabla"]).any() and set(gdp["Varijabla"]) == {"Hrvatska", "Austrija"}
    assert set(gdp["Skupina"]) == {"Hrvatska", "Ostale zemlje"} and set(gdp["Kategorija"]) == {"Podudarni: proizvodnja"}
    assert gdp["Mjesec"].iloc[0] == "veljača 2015" and gdp["Datum"].iloc[0] == "2015-02-01" and gdp["Datum"].is_monotonic_increasing
    hr = tmp_path / "by_country" / "HR"
    assert sorted(p.name for p in hr.glob("*.csv")) == ["1_vodeci_indikatori.csv", "2_podudarni_proizvodnja.csv", "3_podudarni_potrosnja_trgovina.csv", "5_kasni_indikatori_stecaj.csv", "6_svi_indikatori.csv"]
    everything = pd.read_csv(hr / "6_svi_indikatori.csv")
    assert list(everything.columns) == CHART_COLUMNS and not everything.duplicated(["Datum", "Varijabla"]).any()
    assert (everything.loc[everything["Varijabla"] == "BDP", "Kategorija"] == "Podudarni: proizvodnja").all()
    assert set(pd.read_csv(hr / "3_podudarni_potrosnja_trgovina.csv")["Varijabla"]) == {"BDP"}
    assert set(pd.read_csv(hr / "1_vodeci_indikatori.csv")["Varijabla"]) == {"Građevinske dozvole"}
    values = everything["Odstupanje od trenda (z)"]
    assert values.abs().max() <= 3 and (values.round(3) == values).all()
    bounds = pd.read_csv(tmp_path / "axis_bounds.csv")
    assert {"country", "all", "indicator"} == set(bounds["scope_type"])
    assert bounds.loc[(bounds["scope"] == "ALL") & (bounds["category"] == "ALL"), "cycle_min"].iloc[0] == round(long["cycle_z"].min(), 3)
    per_indicator = bounds[bounds["scope_type"] == "indicator"].set_index("scope")
    assert per_indicator.loc["gdp", "cycle_max"] == round(long.loc[long["indicator_id"] == "gdp", "cycle_z"].max(), 3)


def test_rows_follow_category_order_then_registry_order() -> None:
    """Within a category the indicators keep the order of config/indicators.yaml (the R
    display order), not alphabetical order; GDP leads both supply and demand."""
    countries, indicators, settings = load_countries(), load_indicators(), load_settings()
    time = pd.date_range("2015-02-01", periods=2, freq="MS")
    panel = pd.concat([pd.DataFrame({"country": "HR", "indicator_id": i, "time": time, "mom_z": 0.0, "cycle_z": 0.0})
                       for i in ("retail", "construction", "gdp", "unemployment", "industrial_production", "building_permits")], ignore_index=True)
    long = build_long(panel, countries, indicators, settings)
    assert list(dict.fromkeys(zip(long["category"], long["indicator_id"]))) == [
        ("leading", "building_permits"), ("supply", "gdp"), ("supply", "industrial_production"), ("supply", "construction"),
        ("demand", "gdp"), ("demand", "retail"), ("lagging", "unemployment"),
    ]

