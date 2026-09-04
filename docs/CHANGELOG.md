# Changelog

Changes that affect the published numbers or the indicator set. Newest first.

## 2026-09-04

- Python pipeline replaces the R scripts. The R output is reproduced by the parity test (tag parity-r) and the scripts stay in legacy/ as the reference. Plan and task list: docs/UPDATE_PLAN.md, docs/TASKS.md.
- Filters run on the full available history instead of from 2015. This changes every cycle; for Croatian industrial production the 2020 trough moves from -5.2 to -11.7 percent of trend.
- Long-run trend estimated from the seasonally adjusted series (in logs for growth series) rather than from the Henderson trend; effect under half a percentage point.
- Momentum is the month-on-month change in the cycle, no longer the growth rate of the Henderson trend centred on the sample mean.
- Standardisation uses one reference window for every series (from 2010-01), median and MAD, at least 84 observations; published values are clipped at plus or minus 3 and flagged. The unclipped panel is archived under output/vintages/.
- Unemployment uses the seasonally adjusted series and the Henderson trend like every other indicator (the trend-cycle series was used before; Italy had none and was skipped).
- Indexing to 2021 removed; seasonal adjustment runs on levels.
- X-13 models (ARIMA orders, constant, calendar regressors, outlier set, starting values) are identified once per series and step and frozen in config/x13_models.yaml; the monthly run re-estimates parameters with the model fixed and looks for new outliers only in the last twelve months. The transformation is set by series type: log for growth series, none for balances and spreads. Re-identification at the annual review.
- Trend-method comparison (docs/trend_method_comparison.md): the two-sided HP stays; the last 12 months are flagged provisional in the methodology.
- Series with gaps are interpolated (up to three periods) or cut to the latest contiguous segment; the R scripts misaligned them. Retail is no longer truncated to the wholesale sample.
- Indicators added for every country: economic sentiment indicator, consumer confidence, industry order books and the euro area term spread (levels, not detrended); real gross value added and capacity utilisation on the main clock; house price index and loans to non-financial corporations on a new financial panel. Lagging series (unemployment, bankruptcies, NPL) carry the panel label confirmation. HICP is not added (a price level is not a cycle quantity).
- Removed the OVI business confidence index (Ekonomski institut Zagreb, EIZ), no longer published. The Beamer presentation still shows it.
- Indicator count after these changes: Croatia 29, the other countries up to 26 depending on Eurostat coverage.
