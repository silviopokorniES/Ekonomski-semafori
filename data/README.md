# data/

Manual monthly inputs for Croatia. The `*.xlsx` files in this folder are ignored by git; only this README is tracked, so a fresh clone contains no data files. Never overwrite, move, or delete a file here without being asked (see CLAUDE.md).

## Files

| File | Sheet | Columns (exact header strings) | Source | Coverage (as of 2026-09-04) | Indicator ids |
|---|---|---|---|---|---|
| `prvi_put_reg.xlsx` | `Sheet1` | `time`, `Prvi put registrirana osobna vozila`, `Prvi put registrirana teretna vozila` | Državni zavod za statistiku (DZS), first-time registrations of road vehicles | 2015-01 to 2025-09, 129 rows | `cars_registered`, `trucks_registered` |
| `broj_osiguranika.xlsx` | `Sheet1` | `time`, `Broj osiguranika` | Hrvatski zavod za mirovinsko osiguranje (HZMO), number of insured persons | 2015-01 to 2025-11, 131 rows | `insured_persons` |

Column types: `time` is an Excel date equal to the first day of the month; value columns are integer counts (not seasonally adjusted; the pipeline runs X-13 on them).

Source URLs: to be filled in by the maintainer (DZS first-registration release page; HZMO monthly statistical report). Do not guess them.

## Update procedure

- Who: Silvio Pokorni.
- When: after the DZS and HZMO monthly releases, before running `scripts/run_monthly.py`.
- How: append one row per new month at the bottom of the sheet. Keep the header strings byte-identical to the table above (the config references them by name). Keep `time` as the first day of the month. Do not insert blank rows or notes below the data.
- Keep a private backup of this folder outside git; after untracking, these are the only copies.

## Retired

`ovi.xlsx` (sheet `OVI`, columns `time` and `OVI ` with a trailing space): the EIZ business confidence index, no longer updated. Not read by the Python pipeline. Kept locally only so the R reference scripts can run once for the task 1.2 parity fixtures.

## Note for the R fixture run (task 1.2)

The R scripts read these files by bare file name from the working directory and write their Excel outputs into that same directory. Run R from a scratch copy of this folder, never from `data/` itself.
