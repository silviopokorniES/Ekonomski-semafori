# Legacy R scripts

`samo_hrvatska.R` (Croatia) and `ostale_zemlje.R` (the other 20 countries) produced every release up to September 2026. They are kept unchanged as the reference implementation and are not run.

The Python pipeline reproduces their output: git tag `parity-r` marks the commit where `tests/test_parity.py` matches the R Excel files of 4 September 2026 to the rounding of the published values (43 of 57 country-indicator pairs exactly, the rest explained in the test file). The fixtures that record the R inputs, intermediate steps and outputs (vintage 2026-09-04) were captured by tracing the scripts without editing them; the maintainer keeps them outside the public repository.

Differences between the scripts and the current method are listed in `docs/CHANGELOG.md`. Do not edit the scripts; if a question about the old numbers comes up, run them from a scratch copy of `data/` with R 4.6 and the packages eurostat, ecb, seasonal (x13binary), hpfilter, tempdisagg and openxlsx.
