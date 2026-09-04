"""Cycle, momentum, sign inversion, and z-score.

Inputs: the short-run trend (Henderson D12) and the long-run trend as pd.Series
on the same monthly index; the long-run trend is in logs for the ratio transform.
Outputs: cycle and momentum series; invert flips both for counter-cyclical
indicators; zscore standardises over a reference window. Z-score is always the
last transformation.
Transforms: ratio (cycle = 100 (ln D12 - long-run trend of ln SA), the
percentage gap to first order) or difference (cycle = D12 - long-run trend, for
spreads and survey balances). Momentum is the month-on-month change in the
cycle; mom (the percent change of D12, which R used) survives for the parity mode.
Assumptions: NaN propagates. zscore uses the sample standard deviation (n minus 1)
or the MAD scaled by 1.4826; a window with fewer than min_obs observations or
with zero scale raises ValueError.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

TRANSFORMS = ("ratio", "difference")
SCALES = ("sd", "mad")
COVID_START, COVID_END = pd.Timestamp("2020-03-01"), pd.Timestamp("2021-06-01")


def level(short: pd.Series, transform: str) -> pd.Series:
    """The scale on which the cycle is measured: 100 ln x under ratio, x under difference."""
    if transform == "ratio":
        if (short <= 0).any():
            raise ValueError("ratio transform needs a strictly positive series; use difference")
        return 100 * np.log(short)
    if transform == "difference":
        return short
    raise ValueError(f"transform must be one of {TRANSFORMS}, got {transform!r}")


def cycle(short: pd.Series, long: pd.Series, transform: str = "ratio") -> pd.Series:
    """Gap between the short-run trend and the long-run trend, on the level() scale.
    `long` must already be on that scale (a trend of 100 ln SA under ratio)."""
    return level(short, transform) - long


def cycle_percent_of_trend(short: pd.Series, long: pd.Series) -> pd.Series:
    """Legacy R formula for the parity mode: (D12 - trend) / trend in percent, trend in levels."""
    return ((short - long) / long) * 100


def momentum(cyc: pd.Series) -> pd.Series:
    """Month-on-month change in the cycle: velocity in the (position, velocity) diagram."""
    return cyc.diff()


def mom(short: pd.Series, transform: str = "ratio") -> pd.Series:
    """Legacy momentum: percent change of D12 relative to the absolute previous value
    (NaN where the previous value is numerically zero, as in R) under ratio, first
    difference under difference."""
    if transform not in TRANSFORMS:
        raise ValueError(f"transform must be one of {TRANSFORMS}, got {transform!r}")
    if transform == "difference":
        return short.diff()
    prev = short.shift(1)
    out = (short - prev) / prev.abs() * 100
    return out.where(prev.abs() >= 1e-10)


def invert(frame: pd.DataFrame, counter_cyclical: bool) -> pd.DataFrame:
    """Flip the sign of the cycle and mom columns for counter-cyclical indicators
    (unemployment, bankruptcies, non-performing loans), so that higher always
    means better. Applied before the z-score (it commutes with it)."""
    if not counter_cyclical:
        return frame
    out = frame.copy()
    for col in ("cycle", "mom"):
        out[col] = -out[col]
    return out


def window_mask(index: pd.DatetimeIndex, window: str | date, end: date | None = None) -> pd.Series:
    """Boolean mask of the standardisation window: full, ex_covid (drops 2020-03 to
    2021-06), or a start date; `end` freezes the window at a date."""
    mask = pd.Series(True, index=index)
    if window == "ex_covid":
        mask &= ~((index >= COVID_START) & (index <= COVID_END))
    elif window != "full":
        mask &= index >= pd.Timestamp(window)
    if end is not None:
        mask &= index <= pd.Timestamp(end)
    return mask


def zscore(series: pd.Series, window: str | date = "full", scale: str = "sd", min_obs: int = 1, end: date | None = None) -> pd.Series:
    """Standardise every observation with location and scale estimated on the window
    (mean and sample sd, or median and 1.4826 MAD). All observations are
    standardised, only the parameters come from the window."""
    if scale not in SCALES:
        raise ValueError(f"scale must be one of {SCALES}, got {scale!r}")
    ref = series[window_mask(series.index, window, end)].dropna()
    if len(ref) < min_obs:
        raise ValueError(f"{len(ref)} observations in the standardisation window, need {min_obs}")
    if scale == "sd":
        centre, spread = ref.mean(), ref.std(ddof=1)
    else:
        centre = ref.median()
        spread = 1.4826 * (ref - centre).abs().median()
    if not np.isfinite(spread) or spread == 0:
        raise ValueError("zero scale in the standardisation window (constant series)")
    return (series - centre) / spread
