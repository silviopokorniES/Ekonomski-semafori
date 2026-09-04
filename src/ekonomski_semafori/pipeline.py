"""Run the pipeline for one (country, indicator) pair or for everything.

Inputs: config objects from config.py (Country, Indicator, Settings).
Outputs: run_indicator returns a DataFrame [time, mom_z, cycle_z] over the full
computed sample; run_all returns the long panel [country, indicator_id, time,
mom_z, cycle_z] for every configured pair that ran, and logs each skipped pair
with its reason.
Order per indicator, as in the R process_group: fetch, apply the country
override, optional start truncation, gap handling (see _contiguous), stale-series
guard, disaggregate quarterly to monthly, seasonally adjust unless already
adjusted (X-13 needs at least settings.min_seasonal_obs observations, otherwise
the raw series is used, as in R), short-run trend (Henderson unless
skip_henderson), long-run trend (settings.trend_method), cycle and MoM,
z-score, sign inversion. Inversion commutes with the z-score; task 3.5 moves it
before the z-score to match the documented order.
The first cycle observation is dropped after z-scoring so the frame starts
where MoM starts, exactly as R does (scale then slice(-1)).
Skips versus failures: a pair is skipped (logged, run continues) only for data
reasons (SkippedIndicator, EmptyResponseError, a per-series X13Error). Anything
else (network errors, a missing X-13 binary, a missing local file, a bad
config) aborts the run, so an outage can never be published as "no data".
Temporary parity settings (task 2.3, removed in Phase 3): trend_method
hp_on_d12 estimates the long-run trend from the Henderson trend instead of the
SA series; history_start truncates the fetched Eurostat history the way the R
scripts' sinceTimePeriod filter did.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from ekonomski_semafori import cycle as cyc
from ekonomski_semafori import trend
from ekonomski_semafori.adjust import X13Error, disaggregate, seasonal_adjust, x13_binary
from ekonomski_semafori.config import CONFIG_DIR, Country, Indicator, Settings, check_overrides, merge_override
from ekonomski_semafori.fetch import EmptyResponseError, fetch_ecb, fetch_eurostat, fetch_local

log = logging.getLogger(__name__)

LONG_RUN_TRENDS = {"hp": trend.hp}
MAX_GAP = 3
SKIPPABLE = (EmptyResponseError, X13Error)


class SkippedIndicator(RuntimeError):
    """The pair cannot be computed for a data reason; the message says why."""


def fetch_series(country: Country, indicator: Indicator) -> pd.Series:
    """Fetch the raw series for the pair as a Series indexed by time. Local paths
    are relative to the repository root, not to the working directory."""
    if indicator.source == "eurostat":
        frame = fetch_eurostat(indicator.dataset, indicator.filters, country.code)
    elif indicator.source == "ecb":
        frame = fetch_ecb(indicator.series_key.format(ecb_code=country.ecb_code))
    else:
        frame = fetch_local(CONFIG_DIR.parent / indicator.path, indicator.column)
    return pd.Series(frame["value"].to_numpy(), index=pd.DatetimeIndex(frame["time"]), name=indicator.id)


def _contiguous(series: pd.Series, indicator: Indicator) -> pd.Series:
    """Make the series gap-free. Internal gaps longer than MAX_GAP periods (unless
    impute is set) cut the history: only the segment after the last such gap is
    kept. Remaining gaps are filled by linear interpolation. Both cases are
    logged. The R scripts built a ts from the first date and ignored gaps, which
    misaligned every later month; that behaviour is deliberately not reproduced."""
    full = series.asfreq("MS" if indicator.frequency == "M" else "QS")
    missing = full.isna()
    if not missing.any():
        return full
    run_id = (missing != missing.shift()).cumsum()
    runs = [(group.index[0], group.index[-1], len(group)) for _, group in full[missing].groupby(run_id[missing])]
    long_runs = [r for r in runs if r[2] > MAX_GAP]
    if long_runs and not indicator.impute:
        start, end, length = long_runs[-1]
        full = full[full.index > end]
        log.warning("%s: gap of %d periods from %s to %s, keeping %d observations from %s",
                    indicator.id, length, start.date(), end.date(), int(full.notna().sum()), full.index[0].date())
        missing = full.isna()
    if missing.any():
        log.warning("%s: %d missing periods interpolated", indicator.id, int(missing.sum()))
        full = full.interpolate("linear", limit_area="inside")
    return full


def _prepare(series: pd.Series, indicator: Indicator, settings: Settings, history_start: date | None, as_of: date) -> pd.Series:
    """Truncate, make contiguous, reject stale series, disaggregate, seasonally adjust."""
    if not (series.index.day == 1).all():
        raise ValueError(f"{indicator.id}: time index must be at period start")
    if history_start is not None and indicator.source == "eurostat":
        series = series[series.index >= pd.Timestamp(history_start)]   # R applied sinceTimePeriod to Eurostat only
    if indicator.start is not None:
        series = series[series.index >= pd.Timestamp(indicator.start)]
    series = _contiguous(series.dropna(), indicator)
    last = series.index[-1]
    months_behind = (as_of.year - last.year) * 12 + (as_of.month - last.month)
    if months_behind > settings.min_observations:
        raise SkippedIndicator(f"stale: last observation {last.date()} is {months_behind} months before {as_of}, limit {settings.min_observations}")
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
    as_of: date | None = None,
) -> pd.DataFrame:
    """Compute [time, mom_z, cycle_z] for one pair. `raw` replaces the fetch (tests,
    fixtures); `as_of` is the reference month for the stale-series guard (today
    by default). Raises SkippedIndicator when the pair cannot be computed."""
    indicator = merge_override(indicator, country.overrides.get(indicator.id, {}))
    series = raw if raw is not None else fetch_series(country, indicator)
    sa = _prepare(series.astype(float), indicator, settings, history_start, as_of or date.today())
    short = sa if indicator.skip_henderson else trend.henderson(sa)
    short = short.dropna()
    if len(short) < settings.min_observations:
        raise SkippedIndicator(f"{len(short)} observations after trend extraction, need {settings.min_observations}")
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
    as_of: date | None = None,
) -> pd.DataFrame:
    """Run every configured (country, indicator) pair. Data problems are logged with
    the reason and skipped; infrastructure problems abort the run (see module
    docstring). Config and the X-13 binary are checked once before any fetch."""
    check_overrides(countries, indicators)
    if settings.trend_method != "hp_on_d12" and settings.trend_method not in LONG_RUN_TRENDS:
        raise ValueError(f"trend_method {settings.trend_method!r} has no implementation in pipeline.LONG_RUN_TRENDS")
    log.info("X-13 binary: %s", x13_binary())
    frames = []
    for country in countries.values():
        for indicator in indicators:
            if not indicator.applies_to(country.code):
                continue
            try:
                frame = run_indicator(country, indicator, settings, history_start, as_of=as_of)
            except (SkippedIndicator, *SKIPPABLE) as err:
                log.warning("skipped %s %s: %s: %s", country.code, indicator.id, type(err).__name__, err)
                continue
            frame.insert(0, "indicator_id", indicator.id)
            frame.insert(0, "country", country.code)
            frames.append(frame)
            log.info("done %s %s: %d months, %s to %s", country.code, indicator.id, len(frame), frame["time"].iloc[0].date(), frame["time"].iloc[-1].date())
    if not frames:
        raise RuntimeError("no (country, indicator) pair ran")
    return pd.concat(frames, ignore_index=True)
