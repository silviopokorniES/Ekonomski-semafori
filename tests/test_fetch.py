"""Tests for fetch.py: parsing of source shapes and the empty-response rule.
Tests marked `live` call Eurostat and the ECB; deselect with -m "not live"."""

import pandas as pd
import pytest

from ekonomski_semafori.fetch import (
    EmptyResponseError,
    eurostat_wide_to_long,
    fetch_ecb,
    fetch_eurostat,
    fetch_local,
)


def _wide(periods: list[str], values: list) -> pd.DataFrame:
    return pd.DataFrame([["M", "PRD", "HR", *values]], columns=["freq", "indic_bt", "geo\\TIME_PERIOD", *periods])


def test_eurostat_wide_to_long_monthly() -> None:
    out = eurostat_wide_to_long(_wide(["2020-01", "2020-02", "2020-03"], [None, 101.5, "102.0"]), "x")
    assert list(out["time"]) == [pd.Timestamp("2020-02-01"), pd.Timestamp("2020-03-01")]
    assert out["value"].tolist() == [101.5, 102.0]
    assert out["value"].dtype == float


def test_eurostat_wide_to_long_quarterly_period_start() -> None:
    out = eurostat_wide_to_long(_wide(["2019-Q4", "2020-Q1"], [1.0, 2.0]), "x")
    assert list(out["time"]) == [pd.Timestamp("2019-10-01"), pd.Timestamp("2020-01-01")]


def test_eurostat_all_missing_raises() -> None:
    with pytest.raises(EmptyResponseError):
        eurostat_wide_to_long(_wide(["2020-01", "2020-02"], [None, None]), "x")
    with pytest.raises(EmptyResponseError):
        eurostat_wide_to_long(pd.DataFrame(), "x")


def test_unexpected_period_labels_rejected() -> None:
    with pytest.raises(ValueError):
        eurostat_wide_to_long(_wide(["2020-01-15", "2020-02-15"], [1.0, 2.0]), "x")
    with pytest.raises(ValueError):
        eurostat_wide_to_long(_wide(["2020", "2021"], [1.0, 2.0]), "x")


def test_eurostat_two_series_rejected() -> None:
    wide = pd.concat([_wide(["2020-01"], [1.0]), _wide(["2020-01"], [2.0])])
    with pytest.raises(ValueError):
        eurostat_wide_to_long(wide, "x")


def test_fetch_local(tmp_path) -> None:
    path = tmp_path / "in.xlsx"
    pd.DataFrame({"time": pd.to_datetime(["2015-01-15", "2015-02-01"]), "Broj osiguranika": [10, None]}).to_excel(path, index=False)
    out = fetch_local(path, "Broj osiguranika")
    assert out["time"].tolist() == [pd.Timestamp("2015-01-01")]
    assert out["value"].tolist() == [10.0]
    with pytest.raises(ValueError):
        fetch_local(path, "missing column")
    with pytest.raises(FileNotFoundError):
        fetch_local(tmp_path / "absent.xlsx", "Broj osiguranika")


@pytest.mark.live
def test_live_eurostat_hr_industrial_production() -> None:
    out = fetch_eurostat("sts_inpr_m", {"indic_bt": "PRD", "s_adj": "SCA", "nace_r2": "B-D", "freq": "M", "unit": "I21"}, "HR")
    assert len(out) > 120
    assert out["time"].is_monotonic_increasing
    assert (out["time"].dt.day == 1).all()


@pytest.mark.live
def test_live_ecb_greece_resolves_with_gr() -> None:
    out = fetch_ecb("CBD2.Q.GR.W0.11._Z._Z.A.F.I3632._Z._Z._Z._Z._Z._Z.PC")
    assert len(out) > 20
    assert out["time"].iloc[0].month in (1, 4, 7, 10)


@pytest.mark.live
def test_live_eurostat_italy_trend_cycle_unemployment_is_stale() -> None:
    # Eurostat publishes an Italian TC series only up to 2003-12. It is not empty, so the
    # countries.yaml override to SA (and the stale-series guard in task 2.2) are both needed.
    out = fetch_eurostat("une_rt_m", {"age": "TOTAL", "s_adj": "TC", "sex": "T", "freq": "M", "unit": "THS_PER"}, "IT")
    assert out["time"].max() < pd.Timestamp("2015-01-01")
