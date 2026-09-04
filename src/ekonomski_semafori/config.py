"""Load and validate config/countries.yaml, config/indicators.yaml, config/settings.yaml.

Inputs: YAML files in the config/ directory at the repository root.
Outputs: frozen dataclasses (Country, Indicator, Settings). Loaders raise
ValueError naming the offending entry on any schema violation.
Assumptions: the package is installed in editable mode from the repository
checkout, so CONFIG_DIR resolves relative to this file.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Indicator:
    """One entry of indicators.yaml. countries is None when the entry applies to
    every country. Source-specific fields are None for the other sources."""

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
    dataset: str | None = None
    filters: dict[str, str] | None = None
    series_key: str | None = None
    path: str | None = None
    column: str | None = None

    def applies_to(self, country_code: str) -> bool:
        return self.countries is None or country_code in self.countries


def _parse_indicator(entry: dict[str, Any]) -> Indicator:
    """Validate one raw indicators.yaml entry and build an Indicator."""
    ind_id = entry.get("id")
    if not isinstance(ind_id, str) or not ind_id:
        raise ValueError(f"indicator entry without a string id: {entry}")
    missing = _INDICATOR_REQUIRED - set(entry)
    if missing:
        raise ValueError(f"indicator {ind_id}: missing keys {sorted(missing)}")
    unknown = set(entry) - _INDICATOR_REQUIRED - _ALL_SOURCE_FIELDS - {"skip_henderson"}
    if unknown:
        raise ValueError(f"indicator {ind_id}: unknown keys {sorted(unknown)}")

    category = entry["category"]
    categories = tuple([category] if isinstance(category, str) else category)
    if not categories or len(set(categories)) != len(categories) or not set(categories) <= CATEGORIES:
        raise ValueError(f"indicator {ind_id}: category must be one or more of {sorted(CATEGORIES)}")
    for key, allowed in (("source", SOURCES), ("frequency", FREQUENCIES), ("transform", TRANSFORMS)):
        if entry[key] not in allowed:
            raise ValueError(f"indicator {ind_id}: {key} must be one of {sorted(allowed)}")
    for key in ("already_sa", "counter_cyclical"):
        if not isinstance(entry[key], bool):
            raise ValueError(f"indicator {ind_id}: {key} must be true or false")
    skip_henderson = entry.get("skip_henderson", False)
    if not isinstance(skip_henderson, bool):
        raise ValueError(f"indicator {ind_id}: skip_henderson must be true or false")
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
    forbidden = (_ALL_SOURCE_FIELDS - required) & set(entry)
    if forbidden:
        raise ValueError(f"indicator {ind_id}: keys {sorted(forbidden)} not allowed for source {source}")
    filters = entry.get("filters")
    if filters is not None:
        if not isinstance(filters, dict) or not filters:
            raise ValueError(f"indicator {ind_id}: filters must be a non-empty mapping")
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
