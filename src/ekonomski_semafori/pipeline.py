"""Run the pipeline for one (country, indicator) pair or for everything.

Inputs: config objects from config.py.
Outputs: run_indicator returns a DataFrame [time, mom_z, cycle_z]; run_all
returns the long panel across countries and indicators.
Assumptions: per-indicator failures are logged and skipped, never fatal for the
whole run. Country overrides from countries.yaml are merged over the indicator
entry before fetching. Filters run on full history; output starts at
settings.output_start.
"""
