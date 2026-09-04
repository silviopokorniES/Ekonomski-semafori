"""Ekonomski semafori: business cycle clocks for Croatia and 20 euro area countries.

Pipeline per (country, indicator): fetch -> seasonal adjustment and disaggregation
-> short-run trend (Henderson) and long-run trend (HP or alternative) from the SA
series -> cycle and MoM -> z-score and sign inversion (they commute) -> CSV for Flourish.

Configuration lives in config/*.yaml; see config.py.
"""
