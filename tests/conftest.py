"""Shared test helpers: access to the R parity fixtures under tests/fixtures/<vintage>/."""

from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_vintages() -> list[Path]:
    if not FIXTURES.exists():   # the fixtures are not distributed; the parity tests skip without them
        return []
    return sorted(p for p in FIXTURES.iterdir() if p.is_dir() and (p / "index.csv").exists())


@pytest.fixture(scope="session")
def r_fixtures() -> tuple[Path, pd.DataFrame]:
    """Latest fixture vintage folder and its index (one row per captured R call)."""
    vintages = fixture_vintages()
    if not vintages:
        pytest.skip("no R fixtures under tests/fixtures/<vintage>/")
    folder = vintages[-1]
    return folder, pd.read_csv(folder / "index.csv")


def fixture_pairs(folder: Path, index: pd.DataFrame, country: str, fun: str) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    """(tag, input frame, output frame) for each traced call of `fun` in `country`.
    Inputs and outputs were written consecutively by the harness."""
    rows = index[(index["country"] == country) & (index["fun"] == fun)].sort_values("seq")
    files = sorted((folder / country).glob(f"*_{fun}_*.csv"))
    by_seq = {int(f.name[:4]): f for f in files}
    pairs = []
    for (_, inp), (_, out) in zip(rows.iloc[::2].iterrows(), rows.iloc[1::2].iterrows()):
        assert str(inp["tag"]).startswith("input") and str(out["tag"]).startswith("output"), (inp["seq"], out["seq"])
        pairs.append((str(inp["tag"])[6:], pd.read_csv(by_seq[int(inp["seq"])]), pd.read_csv(by_seq[int(out["seq"])])))
    return pairs
