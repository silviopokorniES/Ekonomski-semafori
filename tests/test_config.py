"""Tests for the config loaders: facts about the registry that a bad edit could break."""

from datetime import date

from ekonomski_semafori.config import load_countries

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
