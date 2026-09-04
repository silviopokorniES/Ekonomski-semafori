"""Unit tests for cycle.py on synthetic series (task 2.1)."""

import numpy as np
import pandas as pd
import pytest

from ekonomski_semafori.cycle import cycle, invert, mom, zscore

IDX = pd.date_range("2020-01-01", periods=5, freq="MS")


def test_cycle_ratio_is_percent_of_long_trend() -> None:
    short = pd.Series([110.0, 100.0, 90.0, 100.0, 105.0], index=IDX)
    long = pd.Series([100.0] * 5, index=IDX)
    assert cycle(short, long).tolist() == [10.0, 0.0, -10.0, 0.0, 5.0]


def test_mom_ratio_uses_absolute_previous_and_blanks_zero() -> None:
    short = pd.Series([100.0, 110.0, 0.0, 5.0, -5.0], index=IDX)
    out = mom(short)
    assert np.isnan(out.iloc[0])
    assert out.iloc[1] == pytest.approx(10.0)
    assert out.iloc[2] == pytest.approx(-100.0)
    assert np.isnan(out.iloc[3])            # previous value is zero
    assert out.iloc[4] == pytest.approx(-200.0)   # (-5 - 5) / |5|


def test_difference_transform_not_yet_available() -> None:
    short = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=IDX)
    with pytest.raises(NotImplementedError):
        cycle(short, short, "difference")
    with pytest.raises(NotImplementedError):
        mom(short, "difference")
    with pytest.raises(ValueError):
        mom(short, "percent")


def test_invert_flips_both_columns_only_when_counter_cyclical() -> None:
    frame = pd.DataFrame({"cycle": [1.0, -2.0], "mom": [0.5, 0.0], "other": [7.0, 8.0]})
    flipped = invert(frame, True)
    assert flipped["cycle"].tolist() == [-1.0, 2.0]
    assert flipped["mom"].tolist() == [-0.5, 0.0]
    assert flipped["other"].tolist() == [7.0, 8.0]
    assert invert(frame, False) is frame


def test_zscore_matches_r_scale_and_handles_constants() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0, np.nan], index=IDX)
    out = zscore(series)
    expected = (series - 2.5) / np.std([1, 2, 3, 4], ddof=1)
    pd.testing.assert_series_equal(out, expected)
    constant = zscore(pd.Series([3.0, 3.0, 3.0], index=IDX[:3]))
    assert constant.isna().all()
    with pytest.raises(NotImplementedError):
        zscore(series, "ex_covid")
