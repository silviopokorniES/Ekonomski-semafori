"""Run the pipeline for one (country, indicator) pair or for everything.

Inputs: config objects from config.py (Country, Indicator, Settings).
Outputs: run_indicator returns a DataFrame [time, mom_z, cycle_z] over the full
computed sample; run_all returns the long panel [country, indicator_id, time,
mom_z, cycle_z] for every configured pair that ran, and logs each skipped pair
with its reason.
Order per indicator, as in the R process_group: fetch, apply the country
override, optional start truncation and gap filling, disaggregate quarterly to
monthly, seasonally adjust unless already adjusted (X-13 needs at least
settings.min_seasonal_obs observations, otherwise the raw series is used, as in
R), short-run trend (Henderson unless skip_henderson), long-run trend
(settings.trend_method), cycle and MoM, z-score, sign inversion.
The first cycle observation is dropped after z-scoring so the frame starts
where MoM starts, exactly as R does (scale then slice(-1)).
Temporary parity settings (task 2.3, removed in Phase 3): trend_method
hp_on_d12 estimates the long-run trend from the Henderson trend instead of the
SA series; history_start truncates the fetched history the way the R scripts'
sinceTimePeriod filter did.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from ekonomski_semafori import cycle as cyc
from ekonomski_semafori import trend
from ekonomski_semafori.adjust import disaggregate, seasonal_adjust
from ekonomski_semafori.config import Country, Indicator, Settings, merge_override
from ekonomski_semafori.fetch import fetch_ecb, fetch_eurostat, fetch_local

log = logging.getLogger(__name__)

LONG_RUN_TRENDS = {"hp": trend.hp}


class SkippedIndicator(RuntimeError):
    """The pair cannot be computed; the message says why."""


def fetch_series(country: Country, indicator: Indicator) -> pd.Series:
    """Fetch the raw series for the pair as a Series indexed by time."""
    if indicator.source == "eurostat":
        frame = fetch_eurostat(indicator.dataset, indicator.filters, country.code)
    elif indicator.source == "ecb":
        frame = fetch_ecb(indicator.series_key.format(ecb_code=country.ecb_code))
    else:
        frame = fetch_local(indicator.path, indicator.column)
    return pd.Series(frame["value"].to_numpy(), index=pd.DatetimeIndex(frame["time"]), name=indicator.id)


def _fill_gaps(series: pd.Series, freq: str) -> pd.Series:
    """Linear interpolation of internal missing periods (impute: true)."""
    full = series.asfreq("MS" if freq == "M" else "QS")
    return full.interpolate("linear", limit_area="inside")


def _prepare(series: pd.Series, indicator: Indicator, settings: Settings, history_start: date | None) -> pd.Series:
    """Truncate, fill gaps, check contiguity, disaggregate, and seasonally adjust."""
    if history_start is not None:
        series = series[series.index >= pd.Timestamp(history_start)]
    if indicator.start is not None:
        series = series[series.index >= pd.Timestamp(indicator.start)]
    if indicator.impute:
        series = _fill_gaps(series, indicator.frequency)
    series = series.dropna()
    expected = pd.date_range(series.index[0], series.index[-1], freq="MS" if indicator.frequency == "M" else "QS")
    if len(series) != len(expected):
        raise SkippedIndicator(f"{len(expected) - len(series)} internal gaps between {series.index[0].date()} and {series.index[-1].date()}")
    if indicator.frequency == "Q":
        series = disaggregate(series)
    if not indicator.already_sa:
        if len(series) >= settings.min_seasonal_obs:
            x13 = settings.x13
            series = seasonal_adjust(series, x13["outlier_types"], x13["outlier_critical"], x13["aictest"])
        else:
            log.warning("%s: only %d observations, X-13 skipped, raw series used", indicator.id, len(series))
    return series


def run_indicator(
    country: Country,
    indicator: Indicator,
    settings: Settings,
    history_start: date | None = None,
    raw: pd.Series | None = None,
) -> pd.DataFrame:
    """Compute [time, mom_z, cycle_z] for one pair. `raw` replaces the fetch (tests,
    fixtures). Raises SkippedIndicator when the pair cannot be computed."""
    indicator = merge_override(indicator, country.overrides.get(indicator.id, {}))
    series = raw if raw is not None else fetch_series(country, indicator)
    sa = _prepare(series.astype(float), indicator, settings, history_start)
    if len(sa) < settings.min_observations:
        raise SkippedIndicator(f"{len(sa)} observations after adjustment, need {settings.min_observations}")
    short = sa if indicator.skip_henderson else trend.henderson(sa)
    short = short.dropna()
    if settings.trend_method == "hp_on_d12":
        long = trend.hp(short, settings.hp_lambda)
    else:
        long = LONG_RUN_TRENDS[settings.trend_method](sa, lam=settings.hp_lambda).reindex(short.index)
    frame = pd.DataFrame({
        "cycle": cyc.cycle(short, long, indicator.transform),
        "mom": cyc.mom(short, indicator.transform),
    })
    standardised = pd.DataFrame({
        "cycle": cyc.zscore(frame["cycle"], settings.zscore_window),
        "mom": cyc.zscore(frame["mom"], settings.zscore_window),
    }).iloc[1:]
    standardised = cyc.invert(standardised, indicator.counter_cyclical)
    out = standardised.rename(columns={"cycle": "cycle_z", "mom": "mom_z"}).reset_index(names="time")
    return out[["time", "mom_z", "cycle_z"]]


def run_all(
    countries: dict[str, Country],
    indicators: list[Indicator],
    settings: Settings,
    history_start: date | None = None,
) -> pd.DataFrame:
    """Run every configured (country, indicator) pair. Failures are logged with the
    reason and skipped; the returned panel holds the pairs that ran."""
    frames = []
    for country in countries.values():
        for indicator in indicators:
            if not indicator.applies_to(country.code):
                continue
            try:
                frame = run_indicator(country, indicator, settings, history_start)
            except Exception as err:  # noqa: BLE001, one bad series must not stop the monthly run
                log.warning("skipped %s %s: %s: %s", country.code, indicator.id, type(err).__name__, err)
                continue
            frame.insert(0, "indicator_id", indicator.id)
            frame.insert(0, "country", country.code)
            frames.append(frame)
            log.info("done %s %s: %d months, %s to %s", country.code, indicator.id, len(frame), frame["time"].iloc[0].date(), frame["time"].iloc[-1].date())
    if not frames:
        raise RuntimeError("no (country, indicator) pair ran")
    return pd.concat(frames, ignore_index=True)
