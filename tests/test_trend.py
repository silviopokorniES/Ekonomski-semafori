"""Parity of trend.py with the R reference on the traced fixtures (tasks 1.4 and 1.5)."""

import numpy as np
import pandas as pd

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
