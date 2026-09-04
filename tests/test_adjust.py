"""Parity of adjust.py with the R reference, on the traced fixtures (tasks 1.3)."""

import numpy as np
import pandas as pd

from conftest import fixture_pairs
from ekonomski_semafori.adjust import disaggregate, seasonal_adjust


def _monthly_index(start: str, n: int) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="MS")


def test_seasonal_adjust_matches_r(r_fixtures) -> None:
    folder, index = r_fixtures
    pairs = fixture_pairs(folder, index, "HR", "adjust_series_x13")
    assert pairs, "no adjust_series_x13 calls captured for HR"
    for tag, inp, out in pairs:
        start = str(inp["start_date"].iloc[0])
        series = pd.Series(inp["value"].to_numpy(dtype=float), index=_monthly_index(start, len(inp)))
        result = seasonal_adjust(series, outlier_types="AO", outlier_critical=4.0, aictest=None)
        expected = out["value"].to_numpy(dtype=float)
        rel = np.max(np.abs(result.to_numpy() - expected) / np.abs(expected))
        assert rel < 1e-3, f"{tag} start {start}: max relative gap {rel:.2e}"


def test_disaggregate_matches_r(r_fixtures) -> None:
    folder, index = r_fixtures
    pairs = fixture_pairs(folder, index, "HR", "disaggregate_q_to_m")
    assert len(pairs) >= 5
    for tag, inp, out in pairs:
        col = [c for c in inp.columns if c != "time"][0]
        quarterly = pd.Series(inp[col].to_numpy(dtype=float), index=pd.to_datetime(inp["time"]))
        result = disaggregate(quarterly)
        assert list(result.index) == list(pd.to_datetime(out["time"])), tag
        gap = np.max(np.abs(result.to_numpy() - out[col].to_numpy(dtype=float)))
        assert gap < 1e-6, f"{tag}: max abs gap {gap:.2e}"
