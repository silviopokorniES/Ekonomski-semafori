"""Trend extraction. Every function has the signature f(sa, **params) -> pd.Series.

Inputs: the seasonally adjusted monthly series `sa` (DatetimeIndex, no gaps,
no missing values).
Outputs: a trend series aligned to sa.index.
Short-run trend: henderson (X-11 final trend-cycle, table D12). Long-run trend:
hp by default; alternatives (hp_onesided, baxter_king, christiano_fitzgerald,
hamilton, bn_ucm) are added in Phase 5. The cycle code must not know which
method produced the trend.
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

import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

from ekonomski_semafori.adjust import ESTIMATE, X13Error, model_blocks, outlier_block, run_x13, x13_binary

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
    same regressor tests with the model, constant and outliers fixed and detection
    over the last 12 months."""
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
        return trend
    log.warning("henderson: X-13 failed on every rung for %s, using a 12-month centered moving average", sa.name)
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
