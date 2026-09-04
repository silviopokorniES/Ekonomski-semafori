"""Parity of trend.py with the R reference on the traced fixtures (tasks 1.4 and 1.5)."""

import numpy as np
import pandas as pd
import pytest

from conftest import fixture_pairs
from ekonomski_semafori.trend import henderson, hp


def test_henderson_matches_r(r_fixtures) -> None:
    folder, index = r_fixtures
    pairs = fixture_pairs(folder, index, "HR", "extract_d12_trend")
    assert len(pairs) >= 15
    worst: dict[str, float] = {}
    for tag, inp, out in pairs:
        col = [c for c in inp.columns if c != "time"][0]
        series = pd.Series(inp[col].to_numpy(dtype=float), index=pd.to_datetime(inp["time"]), name=col)
        result = henderson(series)
        expected = out[f"d12_{col}"].to_numpy(dtype=float)
        worst[tag] = float(np.nanmax(np.abs(result.to_numpy() - expected) / np.abs(expected)))
    bad = {k: v for k, v in worst.items() if not v < 1e-3}
    assert not bad, f"relative gap above 1e-3: {bad}"


def test_frozen_model_spec_and_registry(r_fixtures, tmp_path) -> None:
    from ekonomski_semafori.adjust import model_blocks
    from ekonomski_semafori.config import load_x13_models

    auto, frozen = model_blocks(None, "td easter"), model_blocks({"transform": "log", "arima": "(0 1 1)(0 1 1)", "constant": True, "outliers": ["ao2020.Apr"]}, None)
    assert "automdl" in auto and "function = auto" in auto and "aictest = (td easter)" in auto
    assert "arima{\n  model = (0 1 1)(0 1 1)" in frozen and "function = log" in frozen and "automdl" not in frozen
    assert "variables = (\n    const ao2020.Apr\n  )" in frozen and "aictest" not in frozen
    folder, index = r_fixtures
    tag, inp, out = fixture_pairs(folder, index, "HR", "extract_d12_trend")[0]
    col = [c for c in inp.columns if c != "time"][0]
    series = pd.Series(inp[col].to_numpy(dtype=float), index=pd.to_datetime(inp["time"]), name=col)
    fixed = henderson(series, {"transform": "none", "arima": "(0 1 1)(0 1 1)"})
    assert fixed.notna().sum() == len(series)
    registry = tmp_path / "x13_models.yaml"
    registry.write_text("models:\n  HR:\n    gdp:\n      trend: {transform: log, arima: (0 1 1)(0 1 1)}\n", encoding="utf-8")
    assert load_x13_models(registry) == {("HR", "gdp", "trend"): {"transform": "log", "arima": "(0 1 1)(0 1 1)", "constant": False, "outliers": [], "calendar": [], "ar": [], "ma": []}}
    with_calendar = model_blocks({"transform": "log", "arima": "(0 1 1)", "calendar": ["td", "easter[8]"]}, "td easter")
    assert "td easter[8]" in with_calendar and "aictest" not in with_calendar
    with_starts = model_blocks({"transform": "none", "arima": "(1 0 0)", "ma": [], "ar": [0.5]}, None)
    assert "ar = (0.5)" in with_starts
    registry.write_text("models:\n  HR:\n    gdp:\n      trend: {transform: sqrt, arima: (0 1 1)(0 1 1)}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_x13_models(registry)
    assert load_x13_models(None) == {}
    with pytest.raises(FileNotFoundError):
        load_x13_models(tmp_path / "absent.yaml")


def test_hp_matches_r(r_fixtures) -> None:
    folder, index = r_fixtures
    pairs = fixture_pairs(folder, index, "HR", "hp2")
    assert len(pairs) >= 15
    for tag, inp, out in pairs:
        lam = float(inp["lambda"].iloc[0])
        series = pd.Series(inp["value"].to_numpy(dtype=float), index=pd.RangeIndex(len(inp)))
        result = hp(series, lam)
        gap = np.max(np.abs(result.to_numpy() - out["value"].to_numpy(dtype=float)))
        assert gap < 1e-6, f"hp2 call {tag}: max abs gap {gap:.2e}"
