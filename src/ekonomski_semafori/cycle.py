"""Cycle, momentum, sign inversion, and z-score.

Inputs: the short-run trend (Henderson D12) and the long-run trend (HP or an
alternative) as pd.Series on the same monthly index.
Outputs: cycle and MoM series; invert flips both for counter-cyclical indicators;
zscore standardises over the sample. Z-score is always the last transformation.
Transforms: ratio (cycle as percent of the long-run trend, MoM as percent change
of the short-run trend, as in the R process_group) or difference (level
differences, for spreads and survey balances; task 3.6).
Assumptions: inputs have no missing values except where the trend method leaves
NaN at the ends; NaN propagates. zscore uses the sample standard deviation
(n minus 1), as R's scale(); a constant series gives NaN, not an error.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRANSFORMS = ("ratio", "difference")


def _check_transform(transform: str) -> None:
    if transform not in TRANSFORMS:
        raise ValueError(f"transform must be one of {TRANSFORMS}, got {transform!r}")
    if transform == "difference":
        raise NotImplementedError("difference transform is added in task 3.6")


def cycle(short: pd.Series, long: pd.Series, transform: str = "ratio") -> pd.Series:
    """Gap between the short-run and the long-run trend: percent of the long-run
    trend under ratio, level difference under difference."""
    _check_transform(transform)
    return ((short - long) / long) * 100


def mom(short: pd.Series, transform: str = "ratio") -> pd.Series:
    """Month-on-month momentum of the short-run trend: percent change relative to
    the absolute previous value under ratio (NaN where the previous value is
    numerically zero, as in R), first difference under difference."""
    _check_transform(transform)
    prev = short.shift(1)
    out = (short - prev) / prev.abs() * 100
    return out.where(prev.abs() >= 1e-10)


def invert(frame: pd.DataFrame, counter_cyclical: bool) -> pd.DataFrame:
    """Flip the sign of the cycle and mom columns for counter-cyclical indicators
    (unemployment, bankruptcies, non-performing loans), so that higher always
    means better. Commutes with the z-score; the pipeline applies it after the
    z-score to mirror R until task 3.5 moves it before."""
    if not counter_cyclical:
        return frame
    out = frame.copy()
    for col in ("cycle", "mom"):
        out[col] = -out[col]
    return out


def zscore(series: pd.Series, window: str = "full") -> pd.Series:
    """Standardise with mean and sample standard deviation computed over the full
    sample. window ex_covid (mean and sd excluding 2020-03 to 2021-06) is task 3.7."""
    if window != "full":
        raise NotImplementedError("zscore_window ex_covid is added in task 3.7")
    sd = series.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.nan, index=series.index, name=series.name)
    return (series - series.mean()) / sd
