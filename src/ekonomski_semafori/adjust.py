"""Seasonal adjustment (X-13ARIMA-SEATS) and quarterly-to-monthly disaggregation.

Inputs: a pd.Series with a monthly (seasonal_adjust) or quarterly (disaggregate)
DatetimeIndex at period start.
Outputs: a monthly pd.Series aligned to the input index (seasonal_adjust) or to
the months spanned by the quarters (disaggregate).
Assumptions: the X-13 spec written here reproduces what R's seasonal package
generated for adjust_series_x13 in the reference scripts (SEATS, automdl,
transform auto, outlier types and critical value from settings.yaml, no
automatic regressor tests). run_x13 is shared with trend.henderson. The binary
is located by x13_binary (X13PATH, then PATH); the conda-forge Windows build
crashes with a stack overflow on real series, see README. Adjustment runs on
levels, never on an index. Disaggregation is Denton-Cholette, proportional,
average conversion, as tempdisagg::td(q ~ 1) in R, implemented directly (the
tsdisagg package crashed under pandas 3).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class X13Error(RuntimeError):
    """X-13 could not be found, failed, or did not write a requested table."""


def x13_binary() -> Path:
    """Locate the X-13 executable: the X13PATH folder first (an explicit choice wins),
    then PATH. Both the ASCII and the HTML build are accepted; the HTML build is what
    R's x13binary ships. The conda environment is deliberately not searched: the
    conda-forge Windows build crashes on real series. A missing binary is an
    infrastructure error (FileNotFoundError), never a per-series X13Error."""
    names = ("x13as_ascii.exe", "x13as.exe", "x13ashtml.exe", "x13as_html.exe", "x13as_ascii", "x13as", "x13ashtml")
    folders: list[Path] = []
    if os.environ.get("X13PATH"):
        folders.append(Path(os.environ["X13PATH"]))
    for name in names:
        found = shutil.which(name)
        if found:
            folders.append(Path(found).parent)
    for folder in folders:
        for name in names:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    raise FileNotFoundError("X-13 binary not found: set X13PATH to the folder holding x13as_ascii or x13ashtml (see README)")


def run_x13(series: pd.Series, spec: str, tables: tuple[str, ...]) -> dict[str, pd.Series]:
    """Run X-13 on a monthly series. `spec` holds every block after the series block;
    `tables` names the saved output tables to read back (for example s11, d12).
    Returns each table as a Series aligned to series.index."""
    values = series.to_numpy(dtype=float)
    if not isinstance(series.index, pd.DatetimeIndex) or not np.isfinite(values).all():
        raise ValueError("run_x13 needs a DatetimeIndex and finite values only")
    binary = x13_binary()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        data_lines = [f"{t.year} {t.month} {float(v)!r}" for t, v in zip(series.index, values)]
        (folder / "iofile.dta").write_text("\n".join(data_lines) + "\n", encoding="ascii")
        header = 'series{\n  title = "iofile"\n  file = "iofile.dta"\n  format = "datevalue"\n  period = 12\n}\n\n'
        (folder / "iofile.spc").write_text(header + spec, encoding="ascii")
        proc = subprocess.run([str(binary), "iofile"], cwd=folder, capture_output=True, text=True)
        error_files = [f for f in (folder / "iofile.err", folder / "iofile_err.html") if f.exists()]
        errors = "\n".join(f.read_text(errors="replace") for f in error_files)
        # The HTML build exits 0 even on a spec error, so the text is the only reliable signal.
        if proc.returncode != 0 or "ERROR" in errors or "ERROR:" in proc.stdout:
            raise X13Error(f"x13 failed (exit {proc.returncode}): {errors.strip()[-800:] or proc.stdout[-800:]}")
        for line in errors.splitlines():
            if "WARNING" in line:
                log.warning("x13 %s: %s", series.name, line.strip())
        out: dict[str, pd.Series] = {}
        for table in tables:
            path = folder / f"iofile.{table}"
            if not path.exists():
                raise X13Error(f"x13 did not write table {table}: {errors.strip()[-800:]}")
            frame = pd.read_csv(path, sep="\t", skiprows=2, header=None, names=["date", "value"])
            index = pd.to_datetime(frame["date"].astype(str), format="%Y%m")
            out[table] = pd.Series(frame["value"].to_numpy(dtype=float), index=index).reindex(series.index)
        return out


def seasonal_adjust(
    sa_input: pd.Series,
    outlier_types: str = "AO",
    outlier_critical: float = 4.0,
    aictest: str | None = None,
) -> pd.Series:
    """Final seasonally adjusted series (SEATS s11) with the reference settings.
    aictest None writes an empty regression block, as regression.aictest = NULL in R."""
    regression = f"regression{{\n  aictest = ({aictest})\n}}" if aictest else "regression{\n\n}"
    spec = (
        "transform{\n  function = auto\n}\n\n"
        "seats{\n  noadmiss = yes\n  save = (s11)\n}\n\n"
        f"{regression}\n\n"
        f"outlier{{\n  types = {outlier_types}\n  critical = {outlier_critical:g}\n}}\n\n"
        "automdl{\n\n}\n\n"
        "estimate{\n\n}\n"
    )
    return run_x13(sa_input, spec, ("s11",))["s11"]


def disaggregate(quarterly: pd.Series) -> pd.Series:
    """Denton-Cholette disaggregation of a quarterly series to months with a constant
    indicator and average conversion, as tempdisagg::td(q ~ 1, "denton-cholette",
    conversion = "average") in R: the monthly path minimises the sum of squared
    first differences subject to each quarter's monthly mean equalling the quarterly
    value. Solved as one linear KKT system; matches R to 1e-12 on the fixtures."""
    if not isinstance(quarterly.index, pd.DatetimeIndex) or quarterly.isna().any():
        raise ValueError("disaggregate needs a DatetimeIndex and no missing values")
    q = quarterly.to_numpy(dtype=float)
    n_q, n = len(q), 3 * len(q)
    diff = (np.eye(n, k=1) - np.eye(n))[:-1]
    agg = np.kron(np.eye(n_q), np.full((1, 3), 1 / 3))
    kkt = np.block([[diff.T @ diff, agg.T], [agg, np.zeros((n_q, n_q))]])
    monthly = np.linalg.solve(kkt, np.concatenate([np.zeros(n), q]))[:n]
    first = quarterly.index[0].to_period("Q").to_timestamp(how="start")
    return pd.Series(monthly, index=pd.date_range(first, periods=n, freq="MS"), name=quarterly.name)
