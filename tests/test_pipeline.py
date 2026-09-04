"""Tests for pipeline.py: one end-to-end R comparison (task 2.2; the full sweep is
test_parity.py), the gap policy, the stale-series guard, and the skip-versus-abort
rule of run_all."""

import logging
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from ekonomski_semafori import pipeline
from ekonomski_semafori.config import load_countries, load_indicators, load_settings
from ekonomski_semafori.fetch import EmptyResponseError
from ekonomski_semafori.pipeline import SkippedIndicator, _contiguous, run_all, run_indicator
from ekonomski_semafori.trend import moving_average
from parity import VINTAGE, r_output


@pytest.fixture
def registry():
    countries, indicators, settings = load_countries(), load_indicators(), load_settings()
    return countries, {i.id: i for i in indicators}, settings


def test_run_indicator_reproduces_r_for_industrial_production(r_fixtures, registry) -> None:
    folder, _ = r_fixtures
    countries, indicators, settings = registry
    raw = pd.read_csv(next((folder / "HR").glob("*get_eurostat_sts_inpr_m_M-HR-*.csv")))
    series = pd.Series(raw["values"].to_numpy(float), index=pd.DatetimeIndex(pd.to_datetime(raw["time"])))
    indicator = indicators["industrial_production"]
    out = run_indicator(countries["HR"], indicator, replace(settings, trend_method="hp_on_d12"),
                        history_start=date(2015, 1, 1), raw=series, as_of=VINTAGE).set_index("time")
    expected = r_output(folder, countries["HR"])
    expected = expected[expected["name_hr"] == indicator.name_hr].set_index("time")
    assert out.index[0] == expected.index[0] and out.index[-1] == expected.index[-1]
    joined = out.join(expected[["mom_z", "cycle_z"]], lsuffix="_py", rsuffix="_r")
    for col in ("mom_z", "cycle_z"):
        gap = float(np.max(np.abs(joined[f"{col}_py"] - joined[f"{col}_r"])))
        assert gap < 1e-4, f"{col}: max abs gap {gap:.2e}"


def test_run_indicator_default_method(r_fixtures, registry) -> None:
    """Revised method on the industrial production fixture: log-level cycle against the
    HP trend of the SA series, momentum as the change in the cycle, robust z-score on
    the common window; mechanics checked, numbers are not pinned."""
    folder, _ = r_fixtures
    countries, indicators, settings = registry
    raw = pd.read_csv(next((folder / "HR").glob("*get_eurostat_sts_inpr_m_M-HR-*.csv")))
    series = pd.Series(raw["values"].to_numpy(float), index=pd.DatetimeIndex(pd.to_datetime(raw["time"])))
    out = run_indicator(countries["HR"], indicators["industrial_production"], settings, raw=series, as_of=VINTAGE)
    assert list(out.columns) == ["time", "mom_z", "cycle_z"]
    assert out["time"].iloc[0] == series.index[1] and out["time"].iloc[-1] == series.index[-1]
    assert out[["mom_z", "cycle_z"]].notna().all().all()
    window = out[out["time"] >= pd.Timestamp(settings.zscore_window)]
    assert abs(window["cycle_z"].median()) < 1e-9          # MAD standardisation centres the window on its median
    # momentum is the change in the cycle: after standardisation the two z-scores keep that relation up to scale
    cyc_raw = out["cycle_z"]
    assert np.corrcoef(cyc_raw.diff().dropna(), out["mom_z"].iloc[1:])[0, 1] > 0.999
    bankruptcies = replace(indicators["bankruptcies"], counter_cyclical=True)
    flipped = run_indicator(countries["HR"], bankruptcies, settings, raw=series, as_of=VINTAGE)
    assert np.corrcoef(flipped["cycle_z"], out["cycle_z"])[0, 1] < -0.999      # inversion flips the cycle
    tiny_window = replace(settings, zscore_window=date(2026, 1, 1))
    with pytest.raises(SkippedIndicator, match="standardisation window"):
        run_indicator(countries["HR"], indicators["industrial_production"], tiny_window, raw=series, as_of=VINTAGE)


def test_fetch_series_combines_two_ecb_keys_and_averages_days(registry, monkeypatch) -> None:
    countries, indicators, _ = registry
    days = pd.date_range("2024-01-01", "2024-02-29", freq="B")

    def fake_ecb(key):
        value = 3.0 if key.endswith("SR_10Y") else 1.0
        return pd.DataFrame({"time": days, "value": value + np.arange(len(days)) * 0.0})

    monkeypatch.setattr(pipeline, "fetch_ecb", fake_ecb)
    series = pipeline.fetch_series(countries["HR"], indicators["term_spread"])
    assert list(series.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
    assert series.tolist() == [2.0, 2.0]
    assert series.name == "term_spread"


def test_run_indicator_skips_short_series(registry) -> None:
    countries, indicators, settings = registry
    short = pd.Series(np.linspace(100, 110, 12), index=pd.date_range("2024-01-01", periods=12, freq="MS"))
    with pytest.raises(SkippedIndicator):
        run_indicator(countries["HR"], indicators["industrial_production"], settings, raw=short, as_of=VINTAGE)


def test_run_indicator_skips_stale_series(registry) -> None:
    countries, indicators, settings = registry
    old = pd.Series(np.linspace(100, 110, 60), index=pd.date_range("2000-01-01", periods=60, freq="MS"))
    with pytest.raises(SkippedIndicator, match="stale"):
        run_indicator(countries["HR"], indicators["industrial_production"], settings, raw=old, as_of=VINTAGE)


def _monthly(values: dict[str, float]) -> pd.Series:
    return pd.Series(list(values.values()), index=pd.DatetimeIndex(pd.to_datetime(list(values))))


def test_contiguous_interpolates_short_gaps(registry) -> None:
    _, indicators, _ = registry
    series = _monthly({"2020-01-01": 1.0, "2020-02-01": 2.0, "2020-05-01": 5.0, "2020-06-01": 6.0})
    out = _contiguous(series, indicators["industrial_production"])
    assert out.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_contiguous_keeps_segment_after_last_long_gap(registry) -> None:
    _, indicators, _ = registry
    values = {"2019-01-01": 1.0, "2019-02-01": 2.0, "2019-09-01": 9.0, "2019-10-01": 10.0, "2019-12-01": 12.0, "2020-01-01": 13.0}
    out = _contiguous(_monthly(values), indicators["industrial_production"])
    assert out.index[0] == pd.Timestamp("2019-09-01")          # after the 6-month gap, not after the 1-month gap
    assert out.tolist() == [9.0, 10.0, 11.0, 12.0, 13.0]       # the short gap inside the kept segment is interpolated
    imputed = replace(indicators["industrial_production"], impute=True)
    assert len(_contiguous(_monthly(values), imputed)) == 13   # impute keeps everything


def test_moving_average_matches_zoo_center_alignment() -> None:
    series = pd.Series(np.arange(1.0, 21.0), index=pd.date_range("2020-01-01", periods=20, freq="MS"))
    out = moving_average(series)
    assert np.isnan(out.iloc[4]) and out.iloc[5] == 6.5 and out.iloc[13] == 14.5 and np.isnan(out.iloc[14])


def test_run_all_skips_data_problems_but_aborts_on_infrastructure(registry, monkeypatch, caplog) -> None:
    countries, indicators, settings = registry
    hr = {"HR": countries["HR"]}
    ip, con = indicators["industrial_production"], indicators["construction"]
    good = pd.Series(100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 120)), index=pd.date_range("2016-01-01", periods=120, freq="MS"))

    def fetch(country, indicator):
        if indicator.id == "construction":
            raise EmptyResponseError("no data")
        return good

    monkeypatch.setattr(pipeline, "fetch_series", fetch)
    with caplog.at_level(logging.WARNING):
        panel = run_all(hr, [ip, con], settings, as_of=VINTAGE)
    assert set(panel["indicator_id"]) == {"industrial_production"}
    assert any("skipped HR construction" in r.message and "no data" in r.message for r in caplog.records)

    def outage(country, indicator):
        raise ConnectionError("Eurostat down")

    monkeypatch.setattr(pipeline, "fetch_series", outage)
    with pytest.raises(ConnectionError):
        run_all(hr, [ip], settings, as_of=VINTAGE)
