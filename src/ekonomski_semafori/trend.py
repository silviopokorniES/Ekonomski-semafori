"""Trend extraction. Every function has the signature f(sa, **params) -> pd.Series.

Inputs: the seasonally adjusted monthly series `sa` (DatetimeIndex, no gaps,
no missing values).
Outputs: a trend series aligned to sa.index.
Short-run trend: henderson (X-11 final trend-cycle, table D12). Long-run trend:
hp by default; hp_onesided, baxter_king, christiano_fitzgerald, hamilton and
bn_ucm are the Phase 5 comparators (notebooks, not the monthly run). The cycle
code must not know which method produced the trend.
Assumptions: henderson reproduces extract_d12_trend in the R scripts: three X-13
specs tried in order (automatic model with td and easter tests; fixed airline
model; fixed random walk without outliers), then a 12-month centered moving
average as the last resort. With a frozen model (transform and ARIMA orders from
config/x13_models.yaml) that model is tried first and the automatic ladder is
the fallback. The rung used is logged. A missing X-13 binary is not a
per-series failure and propagates (FileNotFoundError) instead of degrading
every series to the moving average.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.bk_filter import bkfilter
from statsmodels.tsa.filters.cf_filter import cffilter
from statsmodels.tsa.filters.hp_filter import hpfilter

from ekonomski_semafori.adjust import ESTIMATE, FALLBACKS, X13Error, model_blocks, outlier_block, run_x13, x13_binary

log = logging.getLogger(__name__)

_X11 = "x11{\n  save = (d12)\n}\n\n"
_LADDER: tuple[tuple[str, str], ...] = (
    (
        "airline",
        "transform{\n  function = auto\n}\n\n"
        "regression{\n\n}\n\n"
        "outlier{\n\n}\n\n" + _X11 + "arima{\n  model = (0 1 1)(0 1 1)\n}\n\n" + ESTIMATE,
    ),
    (
        "random_walk",
        "transform{\n  function = auto\n}\n\n"
        "regression{\n\n}\n\n" + _X11 + "arima{\n  model = (0 1 0)(0 1 0)\n}\n\n" + ESTIMATE,
    ),
)


def trend_spec(model: dict[str, object] | None, series: pd.Series, transform: str = "auto") -> str:
    """Spec of the trend step: automatic model with td and easter tests and full
    outlier detection when model is None (with the given transform), otherwise the
    frozen model with its constant, calendar regressors and outliers fixed (no
    regressor tests) and detection over the last 12 months."""
    return model_blocks(model, "td easter", transform) + outlier_block(None, None, series, model) + _X11 + ESTIMATE


def henderson(sa: pd.Series, model: dict[str, object] | None = None, transform: str = "auto") -> pd.Series:
    """X-11 final trend-cycle (D12) of a monthly series, with the R fallback ladder."""
    x13_binary()   # raises FileNotFoundError before any per-series fallback can hide it
    rungs = ((("frozen", trend_spec(model, sa)),) if model is not None else ()) + (("automdl", trend_spec(None, sa, transform)),) + _LADDER
    for name, spec in rungs:
        try:
            trend = run_x13(sa, spec, ("d12",))["d12"]
        except X13Error as err:
            log.warning("henderson: rung %s failed for %s: %s", name, sa.name, str(err)[:160])
            continue
        if name != ("frozen" if model is not None else "automdl"):
            log.warning("henderson: %s used rung %s", sa.name, name)
            FALLBACKS.append(f"trend: rung {name}")
        return trend
    log.warning("henderson: X-13 failed on every rung for %s, using a 12-month centered moving average", sa.name)
    FALLBACKS.append("trend: 12-month moving average, X-13 failed on every rung")
    return moving_average(sa)


def moving_average(sa: pd.Series) -> pd.Series:
    """12-month centered moving average with the alignment of
    zoo::rollapply(width = 12, align = "center"), which labels the window one
    position earlier than pandas."""
    return sa.rolling(12, center=True).mean().shift(-1)


def hp(sa: pd.Series, lam: float = 129600.0) -> pd.Series:
    """Two-sided Hodrick-Prescott trend with smoothing parameter lam."""
    _, trend = hpfilter(sa.to_numpy(dtype=float), lamb=lam)
    return pd.Series(trend, index=sa.index, name=sa.name)


# Alternative long-run trends for the Phase 5 comparison. Same signature as hp;
# each returns a Series aligned to sa.index, NaN where the method has no estimate.


def hp_onesided(sa: pd.Series, lam: float = 129600.0, min_obs: int = 36) -> pd.Series:
    """One-sided HP trend: at each month the last value of a two-sided HP fitted to the
    data up to that month only, so the estimate never revises when later data arrive
    (the real-time view). NaN for the first min_obs observations."""
    values = sa.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for t in range(min_obs - 1, len(values)):
        out[t] = hpfilter(values[: t + 1], lamb=lam)[1][-1]
    return pd.Series(out, index=sa.index, name=sa.name)


def baxter_king(sa: pd.Series, high: int = 96, k: int = 36) -> pd.Series:
    """Low-pass trend: the series minus its Baxter-King band-pass component with periods
    from 2 up to high months, so only movements longer than high months remain; k leads
    and lags. The first and last k months are NaN."""
    values = sa.to_numpy(dtype=float)
    cyc = bkfilter(values, low=2, high=high, K=k).ravel()
    trend = np.full(len(values), np.nan)
    trend[k:len(values) - k] = values[k:len(values) - k] - cyc
    return pd.Series(trend, index=sa.index, name=sa.name)


def christiano_fitzgerald(sa: pd.Series, high: int = 96) -> pd.Series:
    """Low-pass trend from the asymmetric Christiano-Fitzgerald filter: the series minus
    its band-pass component with periods from 2 up to high months; defined at every
    month including the ends."""
    values = sa.to_numpy(dtype=float)
    cyc, _ = cffilter(values, low=2, high=high, drift=True)
    return pd.Series(values - np.asarray(cyc).ravel(), index=sa.index, name=sa.name)


def hamilton(sa: pd.Series, h: int = 24, p: int = 12) -> pd.Series:
    """Hamilton (2018) regression filter: the trend at t is the fitted value of a
    regression of y_t on a constant and y_{t-h}, ..., y_{t-h-p+1}; the residual is
    the cycle. NaN for the first h + p - 1 observations. One-sided by construction."""
    y = sa.to_numpy(dtype=float)
    n = len(y)
    rows = list(range(h + p - 1, n))
    x = np.column_stack([np.ones(len(rows))] + [y[[t - h - j for t in rows]] for j in range(p)])
    beta, *_ = np.linalg.lstsq(x, y[rows], rcond=None)
    trend = np.full(n, np.nan)
    trend[rows] = x @ beta
    return pd.Series(trend, index=sa.index, name=sa.name)


def bn_ucm(sa: pd.Series) -> pd.Series:
    """Smoothed level of an unobserved components model with a local linear trend and
    a damped stochastic cycle (Harvey), estimated by maximum likelihood. Slow; for the
    comparison notebook, not the monthly run."""
    from statsmodels.tsa.statespace.structural import UnobservedComponents

    model = UnobservedComponents(sa.to_numpy(dtype=float), level="local linear trend", cycle=True, stochastic_cycle=True, damped_cycle=True)
    result = model.fit(disp=False, maxiter=500)
    return pd.Series(result.smoothed_state[0], index=sa.index, name=sa.name)
