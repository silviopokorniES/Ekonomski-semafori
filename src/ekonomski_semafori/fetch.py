"""Fetch raw series from Eurostat, the ECB Data Portal, or a local Excel file.

Inputs: an indicator entry and a country entry from config.py.
Outputs: a tidy DataFrame with columns [time, value], full available history,
no transformations.
Assumptions: an empty response is an error (raise), never a silent None.
Greece is EL at Eurostat and GR at the ECB; the mapping comes from countries.yaml.
"""
