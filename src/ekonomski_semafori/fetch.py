"""Fetch raw series from Eurostat, the ECB Data Portal, or a local Excel file.

Inputs: dataset code plus filters and a country code (Eurostat), a full series
key (ECB), or a file path plus column name (local Excel).
Outputs: a DataFrame with columns [time, value]: time is a Timestamp at the
first day of the month or quarter, value is float, sorted, no missing values,
full available history. No transformations.
Assumptions: every config entry selects exactly one series. A response with no
non-missing observation is an error (EmptyResponseError), never a silent None.
Greece is EL at Eurostat and GR at the ECB; the caller substitutes the ECB code
into the series key before calling fetch_ecb.
"""

from __future__ import annotations

from pathlib import Path

import eurostat
import pandas as pd
from ecbdata import ecbdata


class EmptyResponseError(RuntimeError):
    """The source answered but contained no usable observation."""


def _periods_to_timestamps(labels: pd.Index) -> pd.DatetimeIndex:
    """Convert Eurostat or ECB period labels (2026-07, 2026-Q1) to period-start Timestamps."""
    freq = "Q" if any("Q" in str(label) for label in labels[:1]) else "M"
    return pd.PeriodIndex(labels.astype(str), freq=freq).to_timestamp(how="start")


def _tidy(values: pd.Series, label: str) -> pd.DataFrame:
    """Drop missing values, parse period labels, and return the [time, value] frame."""
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        raise EmptyResponseError(f"{label}: no non-missing observations")
    out = pd.DataFrame({"time": _periods_to_timestamps(values.index), "value": values.to_numpy(dtype=float)})
    return out.sort_values("time", ignore_index=True)


def eurostat_wide_to_long(wide: pd.DataFrame | None, label: str) -> pd.DataFrame:
    """Turn the one-row wide frame from eurostat.get_data_df into [time, value].
    The wide frame has one column per dimension, then geo\\TIME_PERIOD, then one
    column per period."""
    if wide is None or wide.empty:
        raise EmptyResponseError(f"{label}: empty response")
    if len(wide) != 1:
        raise ValueError(f"{label}: filters select {len(wide)} series, expected exactly one")
    columns = list(wide.columns)
    marker = next(i for i, c in enumerate(columns) if "TIME_PERIOD" in str(c))
    period_columns = columns[marker + 1 :]
    return _tidy(wide.iloc[0][period_columns], label)


def fetch_eurostat(dataset: str, filters: dict[str, str], country: str) -> pd.DataFrame:
    """Fetch one Eurostat series for a country with the given dimension filters."""
    label = f"eurostat {dataset} {country} {filters}"
    wide = eurostat.get_data_df(dataset, filter_pars={**filters, "geo": country})
    return eurostat_wide_to_long(wide, label)


def fetch_ecb(series_key: str) -> pd.DataFrame:
    """Fetch one ECB Data Portal series by its full key (country code already substituted)."""
    frame = ecbdata.get_series(series_key)
    if frame is None or frame.empty or "OBS_VALUE" not in frame.columns:
        raise EmptyResponseError(f"ecb {series_key}: empty response")
    values = pd.Series(frame["OBS_VALUE"].to_numpy(), index=pd.Index(frame["TIME_PERIOD"].astype(str)))
    return _tidy(values, f"ecb {series_key}")


def fetch_local(path: str | Path, column: str) -> pd.DataFrame:
    """Read one column of a local Excel file with a `time` column (first day of month).
    A missing file raises FileNotFoundError; a missing column raises ValueError."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"local input not found: {path}")
    sheet = pd.read_excel(path)
    if "time" not in sheet.columns or column not in sheet.columns:
        raise ValueError(f"{path}: expected columns 'time' and '{column}', found {list(sheet.columns)}")
    values = pd.to_numeric(sheet[column], errors="coerce")
    time = pd.to_datetime(sheet["time"]).dt.to_period("M").dt.to_timestamp(how="start")
    out = pd.DataFrame({"time": time, "value": values}).dropna()
    if out.empty:
        raise EmptyResponseError(f"{path} column '{column}': no non-missing observations")
    return out.sort_values("time", ignore_index=True).astype({"value": float})
