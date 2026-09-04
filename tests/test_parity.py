"""Parity of the Python pipeline with the R reference (task 2.3), on the vintage
2026-09-04 fixtures for HR, AT and EL, with trend_method hp_on_d12 and the R
scripts' 2015-01 history start for Eurostat series.

Every pair not listed in KNOWN_DEVIATIONS or CONSISTENT_SKIPS must match the R
Excel output within 1e-4 (the R output is rounded to 5 decimals, so 5e-6 is the
floor). The stage tests in test_adjust.py and test_trend.py show that each
X-13, disaggregation and HP call reproduces R exactly when given R's own input;
the deviations below are therefore properties of the R scripts or of X-13's
automatic model selection, not port bugs. This file stays as a regression test
for the fetch and adjust layers after the methodology changes (the tolerances
of the deviating pairs are then re-measured)."""

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from conftest import fixture_vintages
from ekonomski_semafori.config import load_countries, load_indicators, load_settings
from ekonomski_semafori.fetch import EmptyResponseError
from ekonomski_semafori.pipeline import run_indicator
from parity import VINTAGE, as_r, r_output, raw_series

COUNTRIES = ("HR", "AT", "EL")

KNOWN_DEVIATIONS = {
    ("HR", "retail"): "R inner-joins retail with wholesale (drop_na), truncating the sample; the port keeps each indicator's own range",
    ("AT", "retail"): "same as HR retail: R sample starts 2021-02 with wholesale",
    ("EL", "retail"): "same as HR retail",
    ("HR", "overnight_stays"): "the Croatia script adjusts tourism with default seas() outlier settings, not AO/4.0",
    ("EL", "overnight_stays"): "R built a monthly ts over a series with two internal gaps, misaligning every later month; the port interpolates the gaps",
    ("HR", "household_consumption"): "X-13 automdl tie: R rounds the disaggregated series to 5 decimals; rounding the Python input reproduces R exactly",
    ("AT", "household_consumption"): "X-13 automdl tie flipped by a 1e-14 input difference; R's own input reproduces R exactly",
    ("EL", "npl"): "X-13 automdl tie on the 5-decimal rounding of R's indexed series; rounded input reproduces R exactly",
    ("HR", "npl"): "X-13 model selection is not scale invariant here: SA on levels (port) and on the 2021 index (R) differ by 16 percent",
}
CONSISTENT_SKIPS = {
    ("AT", "registrations"): "Eurostat rejects sts_rb_m for AT; R got NULL, the port raises",
    ("AT", "bankruptcies"): "same as AT registrations",
    ("EL", "construction"): "Eurostat rejects sts_copr_m for EL; R got NULL, the port raises",
    ("EL", "registrations"): "Eurostat rejects sts_rb_m for EL",
    ("EL", "bankruptcies"): "same as EL registrations",
}


NOT_IN_R = {"esi", "consumer_confidence", "order_books", "term_spread", "gva", "capacity_utilisation", "house_prices", "loans_nfc"}   # added after the R scripts were retired


def _pairs() -> list[tuple[str, str]]:
    indicators = load_indicators()
    return [(code, ind.id) for code in COUNTRIES for ind in indicators if ind.applies_to(code) and ind.id not in NOT_IN_R]


@pytest.fixture(scope="module")
def setup():
    vintages = fixture_vintages()
    if not vintages:
        pytest.skip("no R fixtures")
    folder = vintages[-1]
    countries, indicators = load_countries(), load_indicators()
    settings = replace(load_settings(), trend_method="hp_on_d12")
    outputs = {code: r_output(folder, countries[code]) for code in COUNTRIES}
    return folder, pd.read_csv(folder / "index.csv"), countries, {i.id: i for i in indicators}, settings, outputs


@pytest.mark.parametrize("code,indicator_id", _pairs())
def test_pair_matches_r(setup, code: str, indicator_id: str) -> None:
    folder, index, countries, indicators, settings, outputs = setup
    country, indicator = countries[code], as_r(indicators[indicator_id])
    expected = outputs[code]
    expected = expected[expected["name_hr"] == indicator.name_hr].set_index("time")
    if (code, indicator_id) in CONSISTENT_SKIPS:
        assert expected.empty, "R produced output after all; remove the pair from CONSISTENT_SKIPS"
        with pytest.raises(EmptyResponseError):
            raw_series(folder, index, country, indicator)
        return
    raw = raw_series(folder, index, country, indicator)
    out = run_indicator(country, indicator, settings, history_start=date(2015, 1, 1), raw=raw, as_of=VINTAGE).set_index("time")
    assert not expected.empty, "R has no output for this pair"
    if (code, indicator_id) in KNOWN_DEVIATIONS:
        joined = out.join(expected[["cycle_z"]], lsuffix="_py", rsuffix="_r", how="inner")
        assert joined["cycle_z_py"].corr(joined["cycle_z_r"]) > 0.5, KNOWN_DEVIATIONS[(code, indicator_id)]
        return
    assert out.index[0] == expected.index[0] and out.index[-1] == expected.index[-1]
    joined = out.join(expected[["mom_z", "cycle_z"]], lsuffix="_py", rsuffix="_r")
    for col in ("mom_z", "cycle_z"):
        gap = float(np.max(np.abs(joined[f"{col}_py"] - joined[f"{col}_r"])))
        assert gap < 1e-4, f"{code} {indicator_id} {col}: max abs gap {gap:.2e}"
