"""Load and validate config/countries.yaml, config/indicators.yaml, config/settings.yaml.

Inputs: YAML files in the config/ directory at the repository root.
Outputs: frozen dataclasses (Country, Indicator, Settings). Loaders raise
ValueError naming the offending entry on any schema violation.
Assumptions: the package is installed in editable mode from the repository
checkout, so CONFIG_DIR resolves relative to this file.
"""
