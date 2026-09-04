"""Trend-method comparison (task 5.2): cycles of GDP and industrial production for
Croatia, Germany and the euro area under each long-run trend method, with three
metrics per method: (a) mean absolute revision of the cycle's last point: for each
of the last 24 months, the cycle at that month estimated on the sample ending there
(the real-time value) against the full-sample estimate, (b) agreement of turning points
with the two-sided HP baseline (count, and mean absolute date shift in months),
(c) depth of the 2020 trough relative to the 2009 trough.

Usage (inside the semafori environment, from the repository root):
    python notebooks/trend_comparison.py

Outputs: notebooks/trend_comparison_results.csv and notebooks/figures/<series>.png.
Written as a script rather than a notebook so that it runs top to bottom without a
kernel and its outputs can be diffed. The Eurostat BCC turning-point chronology is
not bundled (it could not be verified from the Eurostat site during the review);
metric (b) therefore compares each method with the two-sided HP, not with BCC.
Font: Oswald if installed; otherwise a condensed system face, and the fallback is
printed, never silent.
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ekonomski_semafori import cycle as cyc  # noqa: E402
from ekonomski_semafori import trend  # noqa: E402
from ekonomski_semafori.config import CONFIG_DIR, load_countries, load_indicators, load_settings, load_x13_models  # noqa: E402
from ekonomski_semafori.pipeline import _prepare, fetch_series, x13_transform  # noqa: E402

log = logging.getLogger("trend_comparison")
METHODS = {
    "hp": trend.hp,
    "hp_onesided": trend.hp_onesided,
    "baxter_king": trend.baxter_king,
    "christiano_fitzgerald": trend.christiano_fitzgerald,
    "hamilton": trend.hamilton,
    "bn_ucm": trend.bn_ucm,
}
SERIES = [("HR", "gdp"), ("HR", "industrial_production"), ("DE", "gdp"), ("DE", "industrial_production"),
          ("EA20", "gdp"), ("EA20", "industrial_production")]
OUT = ROOT / "notebooks"


def setup_font() -> str:
    from matplotlib import font_manager, rcParams

    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Oswald", "Bahnschrift", "Arial Narrow", "Roboto Condensed", "Arial"):
        if name in available:
            rcParams["font.family"] = name
            rcParams["axes.unicode_minus"] = False   # condensed system faces lack the Unicode minus glyph
            if name != "Oswald":
                print(f"Oswald is not installed; using {name} instead.")
            return name
    raise RuntimeError("no usable font found")


def cycle_for(level_short: pd.Series, level_sa: pd.Series, method: str) -> pd.Series:
    long = METHODS[method](level_sa)
    if method == "hp_onesided":
        long = METHODS[method](level_sa, min_obs=36)
    return (level_short - long).dropna()


def turning_points(cycle: pd.Series, phase: int = 6) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    """Peaks and troughs as local extrema over a window of `phase` months each side."""
    values = cycle.to_numpy()
    peaks, troughs = [], []
    for i in range(phase, len(values) - phase):
        window = values[i - phase:i + phase + 1]
        if values[i] == window.max() and (window < values[i]).sum() >= 2 * phase - 1:
            peaks.append(cycle.index[i])
        if values[i] == window.min() and (window > values[i]).sum() >= 2 * phase - 1:
            troughs.append(cycle.index[i])
    return peaks, troughs


def nearest_shift(points: list[pd.Timestamp], reference: list[pd.Timestamp]) -> float:
    if not points or not reference:
        return float("nan")
    ref = np.array([r.to_period("M").ordinal for r in reference])
    return float(np.mean([np.min(np.abs(ref - p.to_period("M").ordinal)) for p in points]))


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    font = setup_font()
    countries, settings = load_countries(), load_settings()
    by_id = {i.id: i for i in load_indicators()}
    models = load_x13_models(CONFIG_DIR / settings.x13_models) if settings.x13_models else {}
    # the euro area aggregate is not a configured country; borrow the Eurostat filters through a temporary Country
    from ekonomski_semafori.config import Country
    countries = dict(countries, EA20=Country("EA20", "Euro area", "Europodručje", "U2", {}))
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    rows = []
    for code, ind_id in SERIES:
        indicator = by_id[ind_id]
        raw = fetch_series(countries[code], indicator).astype(float)
        sa = _prepare(raw, indicator, settings, None, date.today(), models.get((code, ind_id, "sa")))
        short = trend.henderson(sa, models.get((code, ind_id, "trend")), x13_transform(indicator, settings)).dropna()
        level_sa, level_short = cyc.level(sa.reindex(short.index), "ratio"), cyc.level(short, "ratio")
        baseline = cycle_for(level_short, level_sa, "hp")
        base_peaks, base_troughs = turning_points(baseline)
        fig, ax = plt.subplots(figsize=(11, 5.5))
        for method in METHODS:
            try:
                full = cycle_for(level_short, level_sa, method)
                realtime = []
                for k in range(24, 0, -1):   # the cycle at month n-k as it would have been published then
                    part = cycle_for(level_short.iloc[:-k], level_sa.iloc[:-k], method)
                    realtime.append((part.index[-1], part.iloc[-1]))
            except Exception as err:  # noqa: BLE001, a method that fails on one series is reported, not fatal
                log.warning("%s %s %s failed: %s", code, ind_id, method, err)
                continue
            revision = float(np.mean([abs(full.get(when, np.nan) - value) for when, value in realtime]))
            peaks, troughs = turning_points(full)
            trough_2020 = full["2020-01-01":"2021-06-01"].min() if len(full["2020-01-01":"2021-06-01"]) else np.nan
            trough_2009 = full["2008-06-01":"2010-06-01"].min() if len(full["2008-06-01":"2010-06-01"]) else np.nan
            rows.append({
                "country": code, "indicator": ind_id, "method": method,
                "revision_realtime_vs_final_pp": round(revision, 3),
                "peaks": len(peaks), "troughs": len(troughs),
                "peak_shift_vs_hp_months": round(nearest_shift(peaks, base_peaks), 1),
                "trough_shift_vs_hp_months": round(nearest_shift(troughs, base_troughs), 1),
                "trough_2020_pp": round(float(trough_2020), 2), "trough_2009_pp": round(float(trough_2009), 2),
                "ratio_2020_to_2009": round(float(trough_2020 / trough_2009), 2) if trough_2009 and not np.isnan(trough_2009) else np.nan,
                "first_month": full.index[0].date(), "last_month": full.index[-1].date(),
            })
            ax.plot(full["2010-01-01":], label=method, linewidth=1.4 if method == "hp" else 1.0)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_title(f"{indicator.name_en}, {countries[code].name_en}: cycle under six long-run trend methods")
        ax.set_ylabel("Cycle, percent of long-run trend (100 ln D12 minus trend)")
        ax.set_xlabel("Month")
        ax.legend(ncol=3, fontsize=9)
        ax.figure.text(0.01, 0.01, "Source: Eurostat, own calculations (Ekonomski semafori). Trend-cycle: X-11 Henderson; long-run trends as labelled.", fontsize=8)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        fig.savefig(OUT / "figures" / f"{code}_{ind_id}.png", dpi=150)
        plt.close(fig)
        print(f"{code} {ind_id}: done")
    results = pd.DataFrame(rows)
    results.to_csv(OUT / "trend_comparison_results.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print(results.groupby("method")[["revision_realtime_vs_final_pp", "peak_shift_vs_hp_months", "trough_shift_vs_hp_months", "ratio_2020_to_2009"]].mean(numeric_only=True).round(2).to_string())
    print(f"font used: {font}")


if __name__ == "__main__":
    main()
