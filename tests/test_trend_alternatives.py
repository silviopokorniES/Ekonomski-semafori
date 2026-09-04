"""Unit tests for the Phase 5 long-run trend alternatives on a synthetic series:
a linear trend plus a 5-year sine cycle plus small noise. Each method must return a
series aligned to the input and recover the linear trend in the interior within a
tolerance that reflects what the method is designed to do."""

import numpy as np
import pandas as pd
import pytest

from ekonomski_semafori.trend import baxter_king, bn_ucm, christiano_fitzgerald, hamilton, hp, hp_onesided

N = 360
INDEX = pd.date_range("1996-01-01", periods=N, freq="MS")
T = np.arange(N)
LINEAR = 100.0 + 0.2 * T
CYCLE = 5.0 * np.sin(2 * np.pi * T / 60)
NOISE = np.random.default_rng(7).normal(0, 0.3, N)
SERIES = pd.Series(LINEAR + CYCLE + NOISE, index=INDEX, name="synthetic")
INTERIOR = slice(60, N - 60)


def _interior_error(trend: pd.Series) -> float:
    return float(np.nanmax(np.abs(trend.to_numpy()[INTERIOR] - LINEAR[INTERIOR])))


@pytest.mark.parametrize(
    "method,kwargs,tolerance",
    [
        (hp, {}, 0.8),                        # lambda 129,600 passes about 6 percent of a 60-month cycle into the trend
        (baxter_king, {}, 0.6),               # 18 to 96 month band removes the cycle, noise leaks a little
        (christiano_fitzgerald, {}, 1.0),
        (hp_onesided, {}, 5.5),               # the real-time estimate lags the trend by up to the cycle amplitude at the peaks
    ],
)
def test_two_sided_and_one_sided_trends_recover_linear_trend(method, kwargs, tolerance) -> None:
    trend = method(SERIES, **kwargs)
    assert list(trend.index) == list(SERIES.index) and trend.name == "synthetic"
    assert _interior_error(trend) < tolerance


def test_one_sided_hp_revises_more_than_two_sided() -> None:
    assert _interior_error(hp_onesided(SERIES)) > 3 * _interior_error(hp(SERIES))


def test_nan_pattern_at_ends() -> None:
    assert baxter_king(SERIES).isna().sum() == 72 and baxter_king(SERIES).iloc[36:-36].notna().all()
    assert christiano_fitzgerald(SERIES).notna().all()
    assert hp_onesided(SERIES, min_obs=36).isna().sum() == 35
    assert hamilton(SERIES).isna().sum() == 35 and hamilton(SERIES).iloc[35:].notna().all()


def test_hamilton_fits_a_linear_series_exactly_and_leaves_the_cycle_in_the_residual() -> None:
    linear = pd.Series(LINEAR, index=INDEX)
    assert np.nanmax(np.abs(hamilton(linear) - linear)) < 1e-6
    residual = (SERIES - hamilton(SERIES)).dropna()
    assert residual.std() > 2.0                      # the 5-year cycle is not predictable two years ahead by this regression
    assert abs(residual.mean()) < 0.5


def test_bn_ucm_level_is_smooth_and_close_to_the_trend() -> None:
    level = bn_ucm(SERIES)
    assert level.notna().all()
    assert _interior_error(level) < 6.0                # the local linear trend absorbs part of a 5-year cycle
    assert level.diff().abs().max() < 1.0             # but it is a smooth level, not the noisy series
