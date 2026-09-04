"""Load and validate config/countries.yaml, config/indicators.yaml, config/settings.yaml.

Inputs: YAML files in the config/ directory at the repository root.
Outputs: frozen dataclasses (Country, Indicator, Settings). Loaders raise
ValueError naming the offending entry on any schema violation.
Assumptions: the package is installed in editable mode from the repository
checkout, so CONFIG_DIR resolves relative to this file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@dataclass(frozen=True)
class Country:
    """One row of countries.yaml. ecb_code equals code unless overridden.
    overrides maps indicator id -> partial indicator settings for this country."""

    code: str
    name_en: str
    name_hr: str
    ecb_code: str
    overrides: dict[str, dict[str, Any]]


def _read_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_countries(path: Path = CONFIG_DIR / "countries.yaml") -> dict[str, Country]:
    """Read countries.yaml into a dict keyed by Eurostat geo code, validating
    required names and the shape of the overrides block."""
    raw = _read_yaml(path)
    entries = raw.get("countries") if isinstance(raw, dict) else None
    if not isinstance(entries, dict) or not entries:
        raise ValueError(f"{path}: 'countries' must be a non-empty mapping")
    allowed = {"name_en", "name_hr", "ecb_code", "overrides"}
    countries: dict[str, Country] = {}
    for code, entry in entries.items():
        if not isinstance(code, str):
            raise ValueError(f"country key {code!r} must be a quoted string (YAML reads NO as false)")
        if not isinstance(entry, dict):
            raise ValueError(f"country {code}: entry must be a mapping")
        unknown = set(entry) - allowed
        if unknown:
            raise ValueError(f"country {code}: unknown keys {sorted(unknown)}")
        for key in ("name_en", "name_hr"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise ValueError(f"country {code}: '{key}' must be a non-empty string")
        overrides = entry.get("overrides", {})
        if not isinstance(overrides, dict) or not all(
            isinstance(v, dict) for v in overrides.values()
        ):
            raise ValueError(f"country {code}: 'overrides' must map indicator ids to mappings")
        countries[code] = Country(
            code=code,
            name_en=entry["name_en"],
            name_hr=entry["name_hr"],
            ecb_code=str(entry.get("ecb_code", code)),
            overrides=overrides,
        )
    return countries


CATEGORIES = frozenset({"leading", "supply", "demand", "external", "lagging"})
SOURCES = frozenset({"eurostat", "ecb", "local"})
FREQUENCIES = frozenset({"M", "Q"})
TRANSFORMS = frozenset({"ratio", "difference"})

_INDICATOR_REQUIRED = frozenset({
    "id", "name_en", "name_hr", "category", "source", "frequency",
    "already_sa", "transform", "counter_cyclical", "countries",
})
_SOURCE_FIELDS: dict[str, frozenset[str]] = {
    "eurostat": frozenset({"dataset", "filters"}),
    "ecb": frozenset({"series_key"}),
    "local": frozenset({"path", "column"}),
}
_ALL_SOURCE_FIELDS = frozenset().union(*_SOURCE_FIELDS.values())
_INDICATOR_OPTIONAL = frozenset({"skip_henderson", "start", "impute"})


@dataclass(frozen=True)
class Indicator:
    """One entry of indicators.yaml, possibly with a country override merged in.
    countries is None when the entry applies to every country. Source-specific
    fields are None for the other sources. start truncates the fetched series to
    dates on or after it; impute fills internal gaps (both implemented in
    pipeline.py, task 2.2)."""

    id: str
    name_en: str
    name_hr: str
    category: tuple[str, ...]
    source: str
    frequency: str
    already_sa: bool
    transform: str
    counter_cyclical: bool
    countries: tuple[str, ...] | None
    skip_henderson: bool = False
    start: date | None = None
    impute: bool = False
    dataset: str | None = None
    filters: dict[str, str] | None = None
    series_key: str | None = None
    path: str | None = None
    column: str | None = None

    def applies_to(self, country_code: str) -> bool:
        """True when this entry is configured for the given country code."""
        return self.countries is None or country_code in self.countries


def _parse_indicator(entry: dict[str, Any]) -> Indicator:
    """Validate one raw indicators.yaml entry and build an Indicator."""
    ind_id = entry.get("id")
    if not isinstance(ind_id, str) or not ind_id:
        raise ValueError(f"indicator entry without a string id: {entry}")
    missing = _INDICATOR_REQUIRED - set(entry)
    if missing:
        raise ValueError(f"indicator {ind_id}: missing keys {sorted(missing)}")
    unknown = set(entry) - _INDICATOR_REQUIRED - _ALL_SOURCE_FIELDS - _INDICATOR_OPTIONAL
    if unknown:
        raise ValueError(f"indicator {ind_id}: unknown keys {sorted(unknown)}")
    for key in ("name_en", "name_hr"):
        if not isinstance(entry[key], str) or not entry[key]:
            raise ValueError(f"indicator {ind_id}: {key} must be a non-empty string")

    category = entry["category"]
    categories = tuple([category] if isinstance(category, str) else category)
    if not categories or len(set(categories)) != len(categories) or not set(categories) <= CATEGORIES:
        raise ValueError(f"indicator {ind_id}: category must be one or more of {sorted(CATEGORIES)}")
    for key, allowed in (("source", SOURCES), ("frequency", FREQUENCIES), ("transform", TRANSFORMS)):
        if not isinstance(entry[key], str) or entry[key] not in allowed:
            raise ValueError(f"indicator {ind_id}: {key} must be one of {sorted(allowed)}")
    for key in ("already_sa", "counter_cyclical"):
        if not isinstance(entry[key], bool):
            raise ValueError(f"indicator {ind_id}: {key} must be true or false")
    skip_henderson = entry.get("skip_henderson", False)
    impute = entry.get("impute", False)
    if not isinstance(skip_henderson, bool) or not isinstance(impute, bool):
        raise ValueError(f"indicator {ind_id}: skip_henderson and impute must be true or false")
    start = entry.get("start")
    if start is not None and not isinstance(start, date):
        raise ValueError(f"indicator {ind_id}: start must be a date (YYYY-MM-DD)")
    if skip_henderson and not entry["already_sa"]:
        raise ValueError(f"indicator {ind_id}: skip_henderson requires already_sa")

    countries_raw = entry["countries"]
    if countries_raw == "all":
        countries = None
    elif isinstance(countries_raw, list) and countries_raw and all(isinstance(c, str) for c in countries_raw):
        countries = tuple(countries_raw)
    else:
        raise ValueError(f"indicator {ind_id}: countries must be all or a non-empty list of codes")

    source = entry["source"]
    required = _SOURCE_FIELDS[source]
    if required - set(entry):
        raise ValueError(f"indicator {ind_id}: source {source} requires {sorted(required)}")
    for key in required:
        value = entry[key]
        bad = (not isinstance(value, dict) or not value) if key == "filters" else (not isinstance(value, str) or not value)
        if bad:
            raise ValueError(f"indicator {ind_id}: {key} must be a non-empty {'mapping' if key == 'filters' else 'string'}")
    forbidden = (_ALL_SOURCE_FIELDS - required) & set(entry)
    if forbidden:
        raise ValueError(f"indicator {ind_id}: keys {sorted(forbidden)} not allowed for source {source}")
    filters = entry.get("filters")
    if filters is not None:
        if not all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in filters.values()):
            raise ValueError(f"indicator {ind_id}: filter values must be scalars (one entry per series)")
        filters = {k: str(v) for k, v in filters.items()}
        if "freq" in filters and filters["freq"] != entry["frequency"]:
            raise ValueError(f"indicator {ind_id}: filters.freq disagrees with frequency")

    return Indicator(
        id=ind_id,
        name_en=entry["name_en"],
        name_hr=entry["name_hr"],
        category=categories,
        source=source,
        frequency=entry["frequency"],
        already_sa=entry["already_sa"],
        transform=entry["transform"],
        counter_cyclical=entry["counter_cyclical"],
        countries=countries,
        skip_henderson=skip_henderson,
        start=start,
        impute=impute,
        dataset=entry.get("dataset"),
        filters=filters,
        series_key=entry.get("series_key"),
        path=entry.get("path"),
        column=entry.get("column"),
    )


def load_indicators(path: Path = CONFIG_DIR / "indicators.yaml") -> list[Indicator]:
    """Read indicators.yaml into a list of Indicator, validating every entry
    against the schema and rejecting duplicate ids."""
    raw = _read_yaml(path)
    entries = raw.get("indicators") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: 'indicators' must be a non-empty list")
    indicators = [_parse_indicator(e) for e in entries]
    ids = [i.id for i in indicators]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate indicator ids {duplicates}")
    return indicators


def merge_override(base: Indicator, override: dict[str, Any]) -> Indicator:
    """Return a copy of base with a country override applied: top-level keys replace,
    `filters` merges key by key. The result is re-validated through the indicator
    schema, so an override can only produce a valid Indicator."""
    if "id" in override or "countries" in override:
        raise ValueError(f"indicator {base.id}: an override may not change id or countries")
    raw = {k: v for k, v in asdict(base).items() if v is not None}
    raw["category"] = list(base.category)
    raw["countries"] = "all" if base.countries is None else list(base.countries)
    for key, value in override.items():
        if key == "filters" and isinstance(value, dict) and isinstance(raw.get("filters"), dict):
            raw["filters"] = {**raw["filters"], **value}
        else:
            raw[key] = value
    return _parse_indicator(raw)


def check_overrides(countries: dict[str, Country], indicators: list[Indicator]) -> None:
    """Raise ValueError if any country override names an unknown indicator, an
    indicator not configured for that country, or fails the indicator schema."""
    by_id = {i.id: i for i in indicators}
    for country in countries.values():
        for ind_id, override in country.overrides.items():
            if ind_id not in by_id:
                raise ValueError(f"country {country.code}: override for unknown indicator {ind_id}")
            if not by_id[ind_id].applies_to(country.code):
                raise ValueError(f"country {country.code}: override for {ind_id}, which is not configured for it")
            merge_override(by_id[ind_id], override)


TREND_METHODS = frozenset({"hp"})
ZSCORE_WINDOWS = frozenset({"full", "ex_covid"})
_SETTINGS_REQUIRED = frozenset({
    "hp_lambda", "min_observations", "min_seasonal_obs", "output_start",
    "trend_method", "zscore_window", "x13",
})
_X13_KEYS = frozenset({"outlier_types", "outlier_critical", "aictest"})


@dataclass(frozen=True)
class Settings:
    """Pipeline-wide settings from settings.yaml."""

    hp_lambda: float
    min_observations: int
    min_seasonal_obs: int
    output_start: date
    trend_method: str
    zscore_window: str
    x13: dict[str, Any]


def load_settings(path: Path = CONFIG_DIR / "settings.yaml") -> Settings:
    """Read settings.yaml, checking key set, types, and enum values."""
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: settings must be a mapping")
    missing = _SETTINGS_REQUIRED - set(raw)
    unknown = set(raw) - _SETTINGS_REQUIRED
    if missing or unknown:
        raise ValueError(f"{path}: missing keys {sorted(missing)}, unknown keys {sorted(unknown)}")
    if not isinstance(raw["hp_lambda"], (int, float)) or isinstance(raw["hp_lambda"], bool) or raw["hp_lambda"] <= 0:
        raise ValueError(f"{path}: hp_lambda must be a positive number")
    for key in ("min_observations", "min_seasonal_obs"):
        if not isinstance(raw[key], int) or isinstance(raw[key], bool) or raw[key] <= 0:
            raise ValueError(f"{path}: {key} must be a positive integer")
    if not isinstance(raw["output_start"], date):
        raise ValueError(f"{path}: output_start must be a date (YYYY-MM-DD)")
    if raw["trend_method"] not in TREND_METHODS:
        raise ValueError(f"{path}: trend_method must be one of {sorted(TREND_METHODS)}")
    if raw["zscore_window"] not in ZSCORE_WINDOWS:
        raise ValueError(f"{path}: zscore_window must be one of {sorted(ZSCORE_WINDOWS)}")
    x13 = raw["x13"]
    if not isinstance(x13, dict) or set(x13) != _X13_KEYS:
        raise ValueError(f"{path}: x13 must have exactly the keys {sorted(_X13_KEYS)}")
    return Settings(
        hp_lambda=float(raw["hp_lambda"]),
        min_observations=raw["min_observations"],
        min_seasonal_obs=raw["min_seasonal_obs"],
        output_start=raw["output_start"],
        trend_method=raw["trend_method"],
        zscore_window=raw["zscore_window"],
        x13=dict(x13),
    )
