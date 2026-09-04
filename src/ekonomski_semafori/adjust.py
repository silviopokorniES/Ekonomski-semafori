"""Seasonal adjustment (X-13ARIMA-SEATS) and quarterly-to-monthly disaggregation.

Inputs: a pd.Series with a monthly or quarterly DatetimeIndex.
Outputs: a seasonally adjusted monthly pd.Series on levels.
Assumptions: X-13 settings come from settings.yaml (x13 block) and reproduce
adjust_series_x13 in the R scripts; disaggregation is Denton-Cholette with
average conversion. Adjustment runs on levels, never on an index.
"""
