"""Unit tests for cycle.py on synthetic series."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from ekonomski_semafori.cycle import cycle, cycle_percent_of_trend, invert, level, mom, momentum, window_mask, zscore

IDX = pd.date_range("2020-01-01", periods=5, freq="MS")


def test_cycle_is_log_gap_under_ratio_and_level_gap_under_difference() -> None:
    short = pd.Series([110.0, 100.0, 90.0, 100.0, 105.0], index=IDX)
    long_log = pd.Series(100 * np.log(100.0), index=IDX)
    out = cycle(short, long_log, "ratio")
    assert out.iloc[0] == pytest.approx(100 * np.log(1.1))
    assert out.iloc[1] == pytest.approx(0.0)
    assert cycle(short, pd.Series(100.0, index=IDX), "difference").tolist() == [10.0, 0.0, -10.0, 0.0, 5.0]
    with pytest.raises(ValueError):
        level(pd.Series([1.0, 0.0, 2.0, 3.0, 4.0], index=IDX), "ratio")


def test_legacy_percent_of_trend_and_mom() -> None:
    short = pd.Series([110.0, 100.0, 90.0, 100.0, 105.0], index=IDX)
    assert cycle_percent_of_trend(short, pd.Series(100.0, index=IDX)).tolist() == [10.0, 0.0, -10.0, 0.0, 5.0]
    growth = mom(pd.Series([100.0, 110.0, 0.0, 5.0, -5.0], index=IDX))
    assert np.isnan(growth.iloc[0]) and growth.iloc[1] == pytest.approx(10.0)
    assert np.isnan(growth.iloc[3])                       # previous value is zero
    assert growth.iloc[4] == pytest.approx(-200.0)        # (-5 - 5) / |5|
    assert mom(pd.Series([1.0, 3.0, 2.0, 2.0, 5.0], index=IDX), "difference").tolist()[1:] == [2.0, -1.0, 0.0, 3.0]


def test_momentum_is_change_in_cycle() -> None:
    cyc = pd.Series([1.0, 3.0, 2.0, 2.0, 5.0], index=IDX)
    assert momentum(cyc).tolist()[1:] == [2.0, -1.0, 0.0, 3.0]


def test_invert_flips_both_columns_only_when_counter_cyclical() -> None:
    frame = pd.DataFrame({"cycle": [1.0, -2.0], "mom": [0.5, 0.0], "other": [7.0, 8.0]})
    flipped = invert(frame, True)
    assert flipped["cycle"].tolist() == [-1.0, 2.0]
    assert flipped["mom"].tolist() == [-0.5, 0.0]
    assert flipped["other"].tolist() == [7.0, 8.0]
    assert invert(frame, False) is frame


def test_window_mask_variants() -> None:
    index = pd.date_range("2019-01-01", periods=48, freq="MS")
    assert window_mask(index, "full").all()
    start = window_mask(index, date(2021, 1, 1), end=date(2021, 12, 1))
    assert start.sum() == 12


def test_zscore_sd_matches_r_scale_and_mad_is_robust() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0, np.nan], index=IDX)
    expected = (series - 2.5) / np.std([1, 2, 3, 4], ddof=1)
    pd.testing.assert_series_equal(zscore(series), expected)
    with_outlier = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0], index=IDX)
    robust = zscore(with_outlier, scale="mad")
    assert robust.iloc[2] == pytest.approx(0.0)              # median is 3
    assert robust.iloc[4] > 20                                # the outlier does not inflate the scale
    with pytest.raises(ValueError, match="zero scale"):
        zscore(pd.Series([3.0, 3.0, 3.0], index=IDX[:3]))
    with pytest.raises(ValueError):
        zscore(series, window=date(2020, 4, 1), min_obs=3)


def test_zscore_parameters_come_from_window_but_all_observations_are_standardised() -> None:
    index = pd.date_range("2018-01-01", periods=36, freq="MS")
    series = pd.Series(np.arange(36, dtype=float), index=index)
    out = zscore(series, window=date(2019, 1, 1), end=date(2019, 12, 1))
    ref = series["2019-01-01":"2019-12-01"]
    assert out.iloc[0] == pytest.approx((0 - ref.mean()) / ref.std(ddof=1))
    assert len(out.dropna()) == 36
