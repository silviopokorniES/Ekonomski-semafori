"""Tests for the config loaders: facts about the registries that a bad edit could break."""

from datetime import date

from ekonomski_semafori.config import load_countries, load_indicators

R_COUNTRY_VECTOR = "AT BE BG CY EE FI FR DE EL IE IT LV LT LU MT NL PT SK SI ES".split()


def test_countries_count_and_codes() -> None:
    countries = load_countries()
    assert len(countries) == 21
    assert "HR" in countries
    assert set(countries) - {"HR"} == set(R_COUNTRY_VECTOR)


def test_greece_ecb_code() -> None:
    countries = load_countries()
    assert countries["EL"].ecb_code == "GR"
    assert all(c.ecb_code == code for code, c in countries.items() if code != "EL")


def test_overrides() -> None:
    countries = load_countries()
    assert countries["SK"].overrides["npl"]["start"] == date(2018, 1, 1)
    assert countries["BG"].overrides["npl"]["impute"] is True
    assert countries["IT"].overrides["unemployment"]["filters"]["s_adj"] == "SA"
    indicator_ids = {i.id for i in load_indicators()}
    for country in countries.values():
        assert set(country.overrides) <= indicator_ids, country.code


def test_every_indicator_valid() -> None:
    indicators = load_indicators()
    ids = [i.id for i in indicators]
    assert len(ids) == len(set(ids))
    for ind in indicators:
        if ind.source == "eurostat":
            assert ind.dataset and ind.filters
        elif ind.source == "ecb":
            assert ind.series_key and "{ecb_code}" in ind.series_key
        else:
            assert ind.path and ind.path.startswith("data/") and ind.column


def test_indicator_counts() -> None:
    indicators = load_indicators()
    assert sum(i.applies_to("HR") for i in indicators) == 21
    assert sum(i.applies_to("AT") for i in indicators) == 18
    by_id = {i.id: i for i in indicators}
    assert by_id["gdp"].category == ("supply", "demand")
    assert "ovi" not in by_id


def test_unemployment_reproduces_r() -> None:
    unemployment = {i.id: i for i in load_indicators()}["unemployment"]
    assert unemployment.filters["s_adj"] == "TC"
    assert unemployment.skip_henderson is True
