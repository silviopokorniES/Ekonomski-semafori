"""Fetch raw series from Eurostat, the ECB Data Portal, or a local Excel file.

Inputs: dataset code plus filters and a country code (Eurostat), a full series
key (ECB), or a file path plus column name (local Excel).
Outputs: a DataFrame with columns [time, value]: time is a Timestamp at the
first day of the month or quarter, value is float, sorted, no missing values,
full available history. No transformations.
Assumptions: every config entry selects exactly one series. A response with no
non-missing observation, or a 400 from Eurostat (the dimension combination does
not exist for that country, which R received as NULL), is EmptyResponseError:
a data absence the caller may skip. Any other transport or HTTP failure
propagates as a requests exception, and a missing local file as
FileNotFoundError, so that outages are never recorded as "no data".
Greece is EL at Eurostat and GR at the ECB; the caller substitutes the ECB code
into the series key before calling fetch_ecb.
"""

from __future__ import annotations

import re
from pathlib import Path

import eurostat
import pandas as pd
import requests
from ecbdata import ecbdata

_MONTH = re.compile(r"^\d{4}-\d{2}$")
_QUARTER = re.compile(r"^\d{4}-Q[1-4]$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class EmptyResponseError(RuntimeError):
    """The source answered but contained no usable observation."""


def _periods_to_timestamps(labels: pd.Index) -> pd.DatetimeIndex:
    """Convert period labels (2026-07, 2026-Q1 or 2026-07-15, all of one kind) to
    period-start Timestamps; daily labels stay daily and are aggregated by the caller."""
    text = labels.astype(str)
    if all(_MONTH.match(t) for t in text):
        freq = "M"
    elif all(_QUARTER.match(t) for t in text):
        freq = "Q"
    elif all(_DAY.match(t) for t in text):
        return pd.DatetimeIndex(pd.to_datetime(text))
    else:
        raise ValueError(f"period labels are not all YYYY-MM, YYYY-Qn or YYYY-MM-DD: {list(text[:3])}")
    return pd.PeriodIndex(text, freq=freq).to_timestamp(how="start")


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
    column per period. None comes from the library when the response carries no
    data table (an SDMX fault or a table without rows); it is treated as a request
    failure, not as an empty series, so an outage is never recorded as no data."""
    if wide is None:
        raise requests.RequestException(f"{label}: Eurostat returned no data (HTTP error inside the eurostat package)")
    if wide.empty:
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
    try:
        wide = eurostat.get_data_df(dataset, filter_pars={**filters, "geo": country})
    except requests.HTTPError as err:
        if err.response is not None and err.response.status_code == 400:
            raise EmptyResponseError(f"{label}: no such series (HTTP 400)") from err
        raise
    return eurostat_wide_to_long(wide, label)


def fetch_ecb(series_key: str) -> pd.DataFrame:
    """Fetch one ECB Data Portal series by its full key (country code already
    substituted). ecbdata raises a plain Exception on every non-200 status; 404
    means the key does not exist and becomes EmptyResponseError, anything else
    propagates."""
    try:
        frame = ecbdata.get_series(series_key)
    except Exception as err:
        if str(err).startswith("REQUEST ERROR 404"):
            raise EmptyResponseError(f"ecb {series_key}: no such series (HTTP 404)") from err
        raise
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
