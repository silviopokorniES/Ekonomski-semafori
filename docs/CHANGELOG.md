# Changelog

Changes that affect the published numbers or the indicator set. Newest first.

## 2026-09-04

- Python pipeline replaces the R scripts. The R output is reproduced by the parity test (tag parity-r) and the scripts stay in the repository as the reference.
- Filters run on the full available history instead of from 2015. This changes every cycle; for Croatian industrial production the 2020 trough moves from -5.2 to -11.7 percent of trend.
- Long-run trend estimated from the seasonally adjusted series (in logs for growth series) rather than from the Henderson trend; effect under half a percentage point.
- Momentum is the month-on-month change in the cycle, no longer the growth rate of the Henderson trend centred on the sample mean.
- Standardisation uses one reference window for every series (from 2010-01), median and MAD, at least 84 observations; published values are clipped at plus or minus 3 and flagged.
- Unemployment uses the seasonally adjusted series and the Henderson trend like every other indicator (the trend-cycle series was used before; Italy had none and was skipped).
- Indexing to 2021 removed; seasonal adjustment runs on levels.
- Series with gaps are interpolated (up to three periods) or cut to the latest contiguous segment; the R scripts misaligned them. Retail is no longer truncated to the wholesale sample.
- Removed the OVI business confidence index (Ekonomski institut Zagreb, EIZ). The index is no longer published. Croatia now has 21 indicators instead of 22. The Beamer presentation still shows OVI; flagged for the co-authors rather than edited here.
- Started the R to Python port (see UPDATE_PLAN.md and TASKS.md). Numbers are unchanged until Phase 3.
