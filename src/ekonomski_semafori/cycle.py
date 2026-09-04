"""Cycle, momentum, sign inversion, and z-score.

Inputs: short-run and long-run trend series aligned on the same index.
Outputs: cycle and MoM series, then inverted for counter-cyclical indicators,
then z-scored. Z-score is always the last transformation.
Transforms: ratio (percent of long-run trend, percent change of short-run trend)
or difference (level differences, for spreads and survey balances).
"""
