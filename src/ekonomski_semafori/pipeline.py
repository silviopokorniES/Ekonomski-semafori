"""Run the pipeline for one (country, indicator) pair or for everything.

Inputs: config objects from config.py (Country, Indicator, Settings).
Outputs: run_indicator returns a DataFrame [time, mom_z, cycle_z] over the full
computed sample; run_all returns the long panel [country, indicator_id, time,
mom_z, cycle_z] for every configured pair that ran, and logs each skipped pair
with its reason.
Order per indicator: fetch, apply the country override, drop the as_of month and
anything later (a partial month from daily averaging is never published),
optional start truncation, gap handling (see _contiguous), stale-series guard,
disaggregate quarterly to monthly (again without the as_of month), seasonally
adjust unless already adjusted (X-13 needs at least settings.min_seasonal_obs
observations, otherwise the raw series is used), short-run trend (Henderson
unless skip_henderson), long-run trend on the level() scale (HP of 100 ln SA
under the ratio transform, of SA under difference; or the window mean; or zero,
per the indicator's long_run field), cycle, momentum (change in the cycle),
sign inversion, z-score on the reference window. The first row is dropped
because momentum starts one month later.
Skips versus failures: a pair is skipped (logged, run continues) only for data
reasons (SkippedIndicator, EmptyResponseError, a per-series X13Error, too few
observations in the standardisation window). Anything else (network errors, a
missing X-13 binary, a missing local file, a bad config) aborts the run, so an
outage can never be published as "no data". An indicator whose fetch returns
an empty response for every country it applies to aborts the run at the end:
that is a wrong dataset code or filter, not a coverage gap. Pairs that ran
without their frozen model or without a Henderson trend are reported through
run_all's `notes` (collected in adjust.FALLBACKS).
Parity mode: trend_method hp_on_d12 runs the R reference formulas (_legacy) and
history_start truncates the Eurostat history as the R scripts' sinceTimePeriod
filter did; both exist only for tests/test_parity.py.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from ekonomski_semafori import cycle as cyc
from ekonomski_semafori import trend
from ekonomski_semafori.adjust import FALLBACKS, X13Error, disaggregate, seasonal_adjust, x13_binary
from ekonomski_semafori.config import CONFIG_DIR, Country, Indicator, Settings, check_overrides, load_x13_models, merge_override
from ekonomski_semafori.fetch import EmptyResponseError, fetch_ecb, fetch_eurostat, fetch_local

log = logging.getLogger(__name__)

MAX_GAP = 3
SKIPPABLE = (EmptyResponseError, X13Error)


class SkippedIndicator(RuntimeError):
    """The pair cannot be computed for a data reason; the message says why."""


def fetch_series(country: Country, indicator: Indicator) -> pd.Series:
    """Fetch the raw series for the pair as a Series indexed by time. Local paths
    are relative to the repository root, not to the working directory. An ECB
    entry with two keys is the difference of the two series (first minus second);
    daily sources are averaged to months when the indicator says aggregate: mean."""
    if indicator.source == "eurostat":
        series = _as_series(fetch_eurostat(indicator.dataset, indicator.filters, country.code))
    elif indicator.source == "ecb":
        keys = [k.format(ecb_code=country.ecb_code) for k in indicator.series_key.split(" - ")]
        parts = [_as_series(fetch_ecb(k)) for k in keys]
        series = parts[0] if len(parts) == 1 else (parts[0] - parts[1]).dropna()
    else:
        series = _as_series(fetch_local(CONFIG_DIR.parent / indicator.path, indicator.column))
    if indicator.aggregate == "mean":
        series = series.resample("MS").mean().dropna()
    return series.rename(indicator.id)


def _as_series(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(frame["value"].to_numpy(), index=pd.DatetimeIndex(frame["time"]))


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


Models = dict[tuple[str, str, str], dict[str, str]]


def x13_transform(indicator: Indicator, settings: Settings) -> str:
    """X-13 transformation by series type: log (multiplicative) for growth series,
    none for balances and spreads. The parity mode keeps R's automatic choice."""
    if settings.trend_method == "hp_on_d12":
        return "auto"
    return "log" if indicator.transform == "ratio" else "none"


def prepare_input(series: pd.Series, indicator: Indicator, settings: Settings, history_start: date | None, as_of: date) -> pd.Series:
    """The monthly series the adjustment step receives: without the as_of month and
    anything later, truncated to the indicator's start, contiguous, rejected if
    stale, disaggregated if quarterly. Shared with scripts/identify_x13_models.py
    so the models are identified on exactly what the monthly run adjusts."""
    if not (series.index.day == 1).all():
        raise ValueError(f"{indicator.id}: time index must be at period start")
    cutoff = pd.Timestamp(as_of.year, as_of.month, 1)
    series = series[series.index < cutoff]
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
        series = series[series.index < cutoff]
    return series


def _prepare(series: pd.Series, indicator: Indicator, settings: Settings, history_start: date | None, as_of: date, model: dict[str, str] | None = None) -> pd.Series:
    """prepare_input, then seasonal adjustment unless the source is already adjusted."""
    series = prepare_input(series, indicator, settings, history_start, as_of)
    if not indicator.already_sa:
        if len(series) >= settings.min_seasonal_obs:
            x13 = settings.x13
            series = seasonal_adjust(series, x13["outlier_types"], x13["outlier_critical"], x13["aictest"], model, x13_transform(indicator, settings))
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
    models: Models | None = None,
) -> pd.DataFrame:
    """Compute [time, mom_z, cycle_z] for one pair. `raw` replaces the fetch (tests,
    fixtures); `as_of` is the reference month for the stale-series guard (today
    by default); `models` is the frozen X-13 registry (automatic selection when a
    pair has no entry). Raises SkippedIndicator when the pair cannot be computed.
    After the call adjust.FALLBACKS lists the steps that did not use the frozen model."""
    indicator = merge_override(indicator, country.overrides.get(indicator.id, {}))
    models = models or {}
    series = raw if raw is not None else fetch_series(country, indicator)
    FALLBACKS.clear()
    sa = _prepare(series.astype(float), indicator, settings, history_start, as_of or date.today(), models.get((country.code, indicator.id, "sa")))
    trend_model = models.get((country.code, indicator.id, "trend"))
    if models and trend_model is None and not indicator.skip_henderson:
        FALLBACKS.append("trend: no frozen model, automatic selection")
    short = sa if indicator.skip_henderson else trend.henderson(sa, trend_model, x13_transform(indicator, settings))
    short = short.dropna()
    if len(short) < settings.min_observations:
        raise SkippedIndicator(f"{len(short)} observations after trend extraction, need {settings.min_observations}")
    if settings.trend_method == "hp_on_d12":
        return _legacy(short, indicator, settings)
    sa = sa.reindex(short.index)
    if indicator.transform == "ratio" and ((sa <= 0).any() or (short <= 0).any()):
        raise SkippedIndicator(f"non-positive values after adjustment (min SA {sa.min():.4g}, min trend {short.min():.4g}); the ratio transform needs a positive series")
    level_sa = cyc.level(sa, indicator.transform)
    if indicator.long_run == "hp":
        long = trend.hp(level_sa, lam=settings.hp_lambda)
    elif indicator.long_run == "mean":
        long = pd.Series(level_sa[cyc.window_mask(level_sa.index, settings.zscore_window, settings.zscore_end)].mean(), index=short.index)
    else:
        long = pd.Series(0.0, index=short.index)
    cycle = cyc.cycle(short, long, indicator.transform)
    mom = cyc.momentum(cycle)
    frame = cyc.invert(pd.DataFrame({"cycle": cycle, "mom": mom}).iloc[1:], indicator.counter_cyclical)
    try:
        standardised = pd.DataFrame({
            col: cyc.zscore(frame[col], settings.zscore_window, settings.zscore_scale, settings.zscore_min_obs, settings.zscore_end)
            for col in ("cycle", "mom")
        })
    except ValueError as err:
        raise SkippedIndicator(str(err)) from err
    out = standardised.rename(columns={"cycle": "cycle_z", "mom": "mom_z"}).reset_index(names="time")
    return out[["time", "mom_z", "cycle_z"]]


def _legacy(short: pd.Series, indicator: Indicator, settings: Settings) -> pd.DataFrame:
    """The R reference computation, kept for the parity regression test: HP on the
    Henderson trend in levels, cycle in percent of trend, percent change of the
    trend as momentum, z-score on the full sample with mean and sd, then the
    first row dropped and the sign inverted."""
    long = trend.hp(short, settings.hp_lambda)
    frame = pd.DataFrame({"cycle": cyc.cycle_percent_of_trend(short, long), "mom": cyc.mom(short, indicator.transform)})
    standardised = pd.DataFrame({col: cyc.zscore(frame[col]) for col in ("cycle", "mom")}).iloc[1:]
    standardised = cyc.invert(standardised, indicator.counter_cyclical)
    out = standardised.rename(columns={"cycle": "cycle_z", "mom": "mom_z"}).reset_index(names="time")
    return out[["time", "mom_z", "cycle_z"]]


def run_all(
    countries: dict[str, Country],
    indicators: list[Indicator],
    settings: Settings,
    history_start: date | None = None,
    as_of: date | None = None,
    skips: list[tuple[str, str, str]] | None = None,
    notes: list[tuple[str, str, str]] | None = None,
) -> pd.DataFrame:
    """Run every configured (country, indicator) pair. Data problems are logged with
    the reason and skipped (and appended to `skips` as (country, indicator, reason)
    when a list is given); pairs that ran without their frozen model or Henderson
    trend are appended to `notes` as (country, indicator, note); infrastructure
    problems abort the run (see module docstring). Config and the X-13 binary are
    checked once before any fetch."""
    check_overrides(countries, indicators)
    log.info("X-13 binary: %s", x13_binary())
    models = load_x13_models(CONFIG_DIR.parent / settings.x13_models if settings.x13_models else None)
    log.info("frozen X-13 models: %d entries%s", len(models), "" if models else " (automatic selection everywhere)")
    frames = []
    empty: dict[str, int] = {}
    for country in countries.values():
        for indicator in indicators:
            if not indicator.applies_to(country.code):
                continue
            try:
                frame = run_indicator(country, indicator, settings, history_start, as_of=as_of, models=models)
            except (SkippedIndicator, *SKIPPABLE) as err:
                log.warning("skipped %s %s: %s: %s", country.code, indicator.id, type(err).__name__, err)
                if skips is not None:
                    skips.append((country.code, indicator.id, f"{type(err).__name__}: {err}"))
                if isinstance(err, EmptyResponseError):
                    empty[indicator.id] = empty.get(indicator.id, 0) + 1
                continue
            if notes is not None:
                notes.extend((country.code, indicator.id, note) for note in FALLBACKS)
            frame.insert(0, "indicator_id", indicator.id)
            frame.insert(0, "country", country.code)
            frames.append(frame)
            log.info("done %s %s: %d months, %s to %s", country.code, indicator.id, len(frame), frame["time"].iloc[0].date(), frame["time"].iloc[-1].date())
    for indicator in indicators:
        applicable = sum(indicator.applies_to(code) for code in countries)
        if applicable > 1 and empty.get(indicator.id, 0) == applicable:
            raise RuntimeError(f"{indicator.id}: empty response for all {applicable} countries; check the dataset code, filters or series key")
    if not frames:
        raise RuntimeError("no (country, indicator) pair ran")
    return pd.concat(frames, ignore_index=True)
