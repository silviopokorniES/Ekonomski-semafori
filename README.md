# Ekonomski semafori

Monthly business cycle clocks for Croatia and 20 other European countries, published as animated scatter plots in Flourish. For each indicator the pipeline computes where its trend-cycle stands relative to its long-run trend (the cycle) and how fast that position is changing (momentum), standardises both, and writes the files the charts read.

Developed at the Faculty of Economics and Business, University of Zagreb (EFZG). Methodology: [business_cycle_methodology.md](business_cycle_methodology.md). Changes that affect the numbers: [docs/CHANGELOG.md](docs/CHANGELOG.md).

## Layout

```
config/          countries.yaml, indicators.yaml, settings.yaml, x13_models.yaml: everything an indicator needs is here, not in code
src/ekonomski_semafori/
  fetch.py       Eurostat, ECB and local Excel readers; raise on empty responses
  adjust.py      X-13ARIMA-SEATS seasonal adjustment, Denton-Cholette disaggregation
  trend.py       Henderson trend-cycle, Hodrick-Prescott trend
  cycle.py       cycle, momentum, sign inversion, standardisation
  pipeline.py    one (country, indicator) pair, or all of them
  output.py      CSV master and per-indicator files, axis bounds, legacy Excel workbooks
scripts/         run_monthly.py (the monthly run), identify_x13_models.py (annual re-identification of the X-13 models)
data/            Croatian Excel inputs (not tracked; see data/README.md)
tests/           unit tests (the parity tests against the R reference need fixtures the maintainer keeps locally; they skip without them)
legacy/          the R scripts that produced releases up to 2026; kept as the reference, not run
docs/            changelog and the trend-method comparison
notebooks/       comparison scripts and their results (not part of the monthly run)
```

## Setup

```bash
conda env create -f environment.yml
conda activate semafori
python -m pip install -e .
```

The pipeline calls the Census X-13ARIMA-SEATS executable directly, so the binary is installed separately and found through the `X13PATH` environment variable (a folder containing `x13as_ascii`, `x13as` or `x13ashtml`). Do not use the conda-forge `x13as` package on Windows: its build exits with a stack overflow on series of realistic length. Two builds that work: the official Census build (https://www.census.gov/data/software/x13as.html, unzip into a folder without spaces, then `setx X13PATH C:\x13as`), or the one shipped with the R package `x13binary` (`setx X13PATH "%LOCALAPPDATA%\R\win-library\4.6\x13binary\bin"`). To make the setting part of the environment:

```bash
conda env config vars set X13PATH=<folder> -n semafori
```

Check it with `python -c "from ekonomski_semafori.adjust import x13_binary; print(x13_binary())"`.

## Monthly run

1. Update the two Croatian Excel inputs (data/README.md).
2. Once a year, re-identify the X-13 models with `python scripts/identify_x13_models.py`, compare the registry with the committed one, and commit.
3. Run:

```bash
python scripts/run_monthly.py
```

The run takes about 25 minutes for 21 countries. It writes to `output/`: `all_countries_long.csv` (one row per indicator, category, country and month from February 2015), `by_indicator/<id>.csv`, `axis_bounds.csv`, `legacy/` (the Excel layout the current Flourish charts use), `logs/<date>.log`, `Processing_Summary.csv` (what ran and what was skipped, with reasons), and `vintages/<date>.csv` (the unclipped panel, archived for revision analysis). Data problems (a series Eurostat does not publish for a country, a stale series) are skipped and listed; a network failure or a missing binary stops the run, so an outage is never published as missing data.

Master file columns: `time` (ISO date), `label` (Croatian month and year), `country`, `country_name`, `category`, `panel` (main, confirmation or financial), `indicator_id`, `indicator_name_hr`, `indicator_name_en`, `mom_z`, `cycle_z`, `clipped`. Files are UTF-8 with a byte order mark so Excel shows diacritics.

## Adding an indicator

Add an entry to `config/indicators.yaml` (source, dataset and filters or series key or local file, frequency, whether adjusted at source, transform, long-run trend, category, names in both languages) and, if it applies to a subset of countries, list them. Country-specific deviations go into `config/countries.yaml` as overrides. No code change should be needed; if one is, the schema is what to fix.

## Tests

```bash
python -m pytest            # unit tests and the parity check against the R fixtures, about a minute
python -m pytest -m live    # three network checks against Eurostat and the ECB
```

The parity test replays the R scripts' configuration on stored fixtures (raw Eurostat data and the R outputs of 4 September 2026, not distributed) and must keep passing after methodology changes; it protects the fetch and adjustment layers. On a fresh clone those tests are skipped.

## Countries

Croatia, plus Austria, Belgium, Bulgaria, Cyprus, Estonia, Finland, France, Germany, Greece, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Portugal, Slovakia, Slovenia and Spain. Croatia has 29 indicators; the others have up to 26, depending on Eurostat coverage.

## Data sources

Eurostat (short-term business statistics, national accounts, balance of payments, unemployment, tourism, business and consumer surveys), the ECB Data Portal (non-performing loans, the AAA yield curve), Državni zavod za statistiku (DZS, vehicle registrations) and Hrvatski zavod za mirovinsko osiguranje (HZMO, insured persons).

## License and contact

MIT License. Silvio Pokorni, [@silviopokorniES](https://github.com/silviopokorniES). Issues: https://github.com/silviopokorniES/Ekonomski-semafori/issues
