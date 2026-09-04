"""Write pipeline results for Flourish.

Inputs: the long panel from pipeline.run_all.
Outputs: output/all_countries_long.csv, output/by_indicator/<id>.csv,
output/axis_bounds.csv, and per-country Excel workbooks in the legacy layout
for one release cycle. CSV files are UTF-8 with BOM, ISO dates, plus a Croatian
month label column.
"""
