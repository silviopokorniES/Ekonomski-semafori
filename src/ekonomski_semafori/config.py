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
