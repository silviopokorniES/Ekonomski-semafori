"""Tests for the config loaders: facts about the registries that a bad edit could break,
and the loader rejections that protect methodological rules."""

from datetime import date
from pathlib import Path

import pytest

from ekonomski_semafori.config import (
    _parse_indicator,
    check_overrides,
    load_countries,
    load_indicators,
    load_settings,
    merge_override,
)

R_COUNTRY_VECTOR = "AT BE BG CY EE FI FR DE EL IE IT LV LT LU MT NL PT SK SI ES".split()

VALID_ENTRY = {
    "id": "x", "name_en": "X", "name_hr": "X", "category": "supply", "source": "eurostat",
    "dataset": "sts_inpr_m", "filters": {"indic_bt": "PRD", "freq": "M"}, "frequency": "M",
    "already_sa": True, "transform": "ratio", "counter_cyclical": False, "countries": "all",
}


def test_countries_count_and_codes() -> None:
    countries = load_countries()
    assert len(countries) == 21
    assert "HR" in countries
    assert set(countries) - {"HR"} == set(R_COUNTRY_VECTOR)


def test_greece_ecb_code() -> None:
    countries = load_countries()
    assert countries["EL"].ecb_code == "GR"
    assert all(c.ecb_code == code for code, c in countries.items() if code != "EL")


def test_overrides_validate_and_merge() -> None:
    countries = load_countries()
    indicators = load_indicators()
    check_overrides(countries, indicators)
    by_id = {i.id: i for i in indicators}
    assert not countries["IT"].overrides
    legacy = merge_override(by_id["unemployment"], {"filters": {"s_adj": "TC"}, "skip_henderson": True})
    assert legacy.filters["s_adj"] == "TC" and legacy.filters["age"] == "TOTAL" and legacy.skip_henderson
    assert merge_override(by_id["npl"], countries["SK"].overrides["npl"]).start == date(2018, 1, 1)
    assert merge_override(by_id["npl"], countries["BG"].overrides["npl"]).impute is True
    with pytest.raises(ValueError):
        merge_override(by_id["npl"], {"id": "other"})


def test_every_indicator_valid() -> None:
    indicators = load_indicators()
    ids = [i.id for i in indicators]
    assert len(ids) == len(set(ids))
    for ind in indicators:
        if ind.source == "eurostat":
            assert ind.dataset and ind.filters
        elif ind.source == "ecb":
            assert ind.series_key
            assert "{ecb_code}" in ind.series_key or ind.id == "term_spread"   # the spread is one euro area series for all
        else:
            assert ind.path and ind.path.startswith("data/") and ind.column


def by_id_long_run(indicators) -> dict[str, str]:
    return {i.id: i.long_run for i in indicators if i.long_run != "hp"}


def test_indicator_counts() -> None:
    indicators = load_indicators()
    assert sum(i.applies_to("HR") for i in indicators) == 25
    assert sum(i.applies_to("AT") for i in indicators) == 22
    assert by_id_long_run(indicators) == {"esi": "mean", "consumer_confidence": "mean", "order_books": "mean", "term_spread": "none"}
    by_id = {i.id: i for i in indicators}
    assert by_id["gdp"].category == ("supply", "demand")
    assert "ovi" not in by_id


def test_unemployment_uses_sa_and_henderson() -> None:
    unemployment = {i.id: i for i in load_indicators()}["unemployment"]
    assert unemployment.filters["s_adj"] == "SA"
    assert unemployment.skip_henderson is False
    assert unemployment.long_run == "hp"


@pytest.mark.parametrize(
    "change",
    [
        {"filters": {"indic_bt": ["PRD", "VOL"], "freq": "M"}},   # multi-value filter: one entry per series
        {"filters": {"indic_bt": "PRD", "freq": "Q"}},            # filters.freq disagrees with frequency
        {"skip_henderson": True, "already_sa": False},             # skipping Henderson needs an adjusted input
        {"dataset": None},                                         # required source field present but empty
        {"category": ["supply", "supply"]},                        # duplicate category
        {"long_run": "none"},                                      # none needs the difference transform
    ],
)
def test_parse_indicator_rejects(change: dict) -> None:
    with pytest.raises(ValueError):
        _parse_indicator({**VALID_ENTRY, **change})


def test_settings(tmp_path: Path) -> None:
    settings = load_settings()
    assert settings.hp_lambda == 129600
    assert settings.output_start == date(2015, 2, 1)
    assert settings.momentum == "cycle_change" and settings.zscore_scale == "mad"
    assert settings.zscore_window == date(2010, 1, 1) and settings.zscore_min_obs == 84 and settings.zscore_end is None
    assert settings.x13 == {"outlier_types": "AO", "outlier_critical": 4.0, "aictest": None}
    bad = tmp_path / "settings.yaml"
    bad.write_text(
        "hp_lambda: 129600\nmin_observations: 24\nmin_seasonal_obs: 36\n"
        "output_start: 2015-02-01\ntrend_method: bandpass\nzscore_window: full\n"
        "momentum: cycle_change\nzscore_scale: mad\nzscore_min_obs: 84\nzscore_end: null\naxis_clip: 3\nx13_models: null\n"
        "x13: {outlier_types: AO, outlier_critical: 4.0, aictest: null}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="trend_method"):
        load_settings(bad)
