"""Trend extraction. Every function has the signature f(sa, **params) -> pd.Series.

Inputs: the seasonally adjusted monthly series `sa`.
Outputs: a trend series aligned to sa.index.
Short-run trend: henderson (X-11 D12). Long-run trend: hp by default; alternatives
(hp_onesided, baxter_king, christiano_fitzgerald, hamilton, bn_ucm) are added in
Phase 5. The cycle code must not know which method produced the trend.
"""
