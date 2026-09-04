"""Annual identification of X-13 models: run the automatic selection once for every
(country, indicator) that uses X-13 and freeze the result in config/x13_models.yaml.

Usage (inside the semafori environment, from the repository root):
    python scripts/identify_x13_models.py [--countries HR,AT] [--output config/x13_models.yaml]

For each pair the script fetches and prepares the series exactly as the monthly run
does, then records the transform (log or none) and the ARIMA orders that X-13's
automatic selection picked for the seasonal adjustment step (unadjusted sources)
and for the trend step (every series with a Henderson trend). The monthly run then
re-estimates the parameters with these models fixed, so month-to-month changes
come from data, not from model re-selection. Re-run at the annual review and
compare the two registries before committing. With --countries or --indicators
the entries not selected are kept from the existing registry.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ekonomski_semafori import trend  # noqa: E402
from ekonomski_semafori.adjust import X13Error, run_x13, sa_spec  # noqa: E402
from ekonomski_semafori.config import load_countries, load_indicators, load_settings, merge_override  # noqa: E402
from ekonomski_semafori.fetch import EmptyResponseError  # noqa: E402
from ekonomski_semafori.pipeline import SkippedIndicator, _prepare, fetch_series, prepare_input, x13_transform  # noqa: E402

log = logging.getLogger("identify_x13_models")


def selected(udg: dict[str, object]) -> dict[str, object]:
    """Transform, ARIMA orders, whether automdl kept a constant term, and the
    automatically identified outliers (from the saved model file)."""
    transform = "log" if str(udg.get("aictrans", udg.get("transform", ""))).lower().startswith("log") else "none"
    regressors = udg.get("regressors", [])
    outliers = [r for r in regressors if r[:2] in ("ao", "ls", "tc") and "." in r]
    calendar = [r for r in regressors if r not in outliers and r != "const"]
    coefficients = udg.get("coefficients", {})
    starts = {name: [round(v, 6) for v in coefficients.get(name, [])] for name in ("ar", "ma")}
    if any(abs(v) >= 0.99 for vals in starts.values() for v in vals):
        starts = {"ar": [], "ma": []}   # a value on the invertibility or stationarity boundary is rejected as a start
    return {"transform": transform, "arima": udg["arimamdl"], "constant": "const" in regressors, "calendar": calendar, "outliers": outliers, **starts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--countries", default=None, help="comma-separated codes; default all")
    parser.add_argument("--indicators", default=None, help="comma-separated indicator ids; default all. With a subset, existing registry entries for other indicators are kept")
    parser.add_argument("--output", type=Path, default=ROOT / "config" / "x13_models.yaml")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    countries, indicators, settings = load_countries(), load_indicators(), load_settings()
    codes = args.countries.split(",") if args.countries else list(countries)
    only = set(args.indicators.split(",")) if args.indicators else None
    if only:
        indicators = [i for i in indicators if i.id in only]
    x13 = settings.x13
    models: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    if (only or args.countries) and args.output.exists():
        models = yaml.safe_load(args.output.read_text(encoding="utf-8")).get("models", {})   # keep the entries not selected
    for code in codes:
        country = countries[code]
        for base in indicators:
            if not base.applies_to(code):
                continue
            indicator = merge_override(base, country.overrides.get(base.id, {}))
            if indicator.already_sa and indicator.skip_henderson:
                continue
            try:
                raw = fetch_series(country, indicator).astype(float)
                steps: dict[str, dict[str, str]] = {}
                if not indicator.already_sa:
                    pre = prepare_input(raw, indicator, settings, None, date.today())   # what the adjustment step receives
                    result = run_x13(pre, sa_spec(x13["outlier_types"], x13["outlier_critical"], x13["aictest"], None, pre, x13_transform(indicator, settings)), ("s11",), diagnostics=True)
                    steps["sa"] = selected(result["udg"])
                sa = _prepare(raw, indicator, settings, None, date.today(), model=None)
                if not indicator.skip_henderson:
                    result = run_x13(sa, trend.trend_spec(None, sa, x13_transform(indicator, settings)), ("d12",), diagnostics=True)
                    steps["trend"] = selected(result["udg"])
                models.setdefault(code, {})[indicator.id] = steps
                log.info("%s %s: %s", code, indicator.id, steps)
            except (SkippedIndicator, EmptyResponseError, X13Error) as err:
                log.warning("%s %s: no model (%s: %s)", code, indicator.id, type(err).__name__, str(err)[:120])
    header = (
        f"# Frozen X-13 models, identified {date.today().isoformat()} by scripts/identify_x13_models.py.\n"
        "# transform: log or none; arima: (p d q)(P D Q); constant: whether the automatic procedure kept a mean term;\n"
        "# calendar: the trading-day and Easter regressors the automatic test chose; outliers: the regressors it\n"
        "# identified (new ones are still detected over the last 12 months each run);\n"
        "# ar, ma: the estimated coefficients, used as starting values so monthly re-estimation stays in the same optimum.\n"
        "# Re-identify at the annual review and diff before committing.\n"
    )
    args.output.write_text(header + yaml.safe_dump({"models": models}, allow_unicode=True, sort_keys=True), encoding="utf-8")
    log.info("wrote %s with %d countries", args.output, len(models))


if __name__ == "__main__":
    main()
