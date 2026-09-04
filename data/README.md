# data/

Manual monthly inputs for Croatia. The `*.xlsx` files in this folder are ignored by git; only this README is tracked, so a fresh clone contains no data files. Never overwrite, move, or delete a file here without being asked (see CLAUDE.md).

## Files

| File | Sheet | Columns (exact header strings) | Source | Coverage (as of 2026-09-04) | Indicator ids |
|---|---|---|---|---|---|
| `prvi_put_reg.xlsx` | `Sheet1` | `time`, `Prvi put registrirana osobna vozila`, `Prvi put registrirana teretna vozila` | Državni zavod za statistiku (DZS), first-time registered road vehicles, total (new and used, all owners): columns are DZS "osobna vozila" and "kamioni" | 2015-01 to 2025-09, 129 rows | `cars_registered`, `trucks_registered` |
| `broj_osiguranika.xlsx` | `Sheet1` | `time`, `Broj osiguranika` | Hrvatski zavod za mirovinsko osiguranje (HZMO), total insured persons at month end | 2015-01 to 2026-07, 139 rows | `insured_persons` |

Column types: `time` is an Excel date equal to the first day of the month; value columns are integer counts (not seasonally adjusted; the pipeline runs X-13 on them).

Sources (verified 2026-09-04):

- HZMO: monthly news item "Prvi rezultati Hrvatskog zavoda za mirovinsko osiguranje o broju osiguranika za <mjesec> <godina>", listed at https://www.mirovinsko.hr/hr/vijesti/114, published around the 6th to 9th of the following month. The value is the sentence "na dan <last day of month> bilježi N osiguranika". Revisions are published as separate "Revidirani službeni podatci" items (June 2025 was revised from 1 768 228 to 1 783 516; the file holds the revised value).
- DZS: "Statistika u nizu", Transport, table "Prvi put registrirana cestovna vozila", Excel file https://podaci.dzs.hr/media/rx4bmpuw/transport-registrirana-cestovna-vozila.xlsx (search https://podaci.dzs.hr/hr/search?q=registrirana if the path changes). The DZS PxWeb API does not carry this series. Annual totals in the file match the DZS releases TRAN-2024-1-2 and TRAN-2025-1-2 (osobna vozila, kamioni).

## Update procedure

- Who: Silvio Pokorni.
- When: after the DZS and HZMO monthly releases, before running `scripts/run_monthly.py`.
- How: read the HZMO figure from the news item and the DZS figures from the Excel above; append one row per new month at the bottom of the sheet. Keep the header strings byte-identical to the table above (the config references them by name). Keep `time` as the first day of the month. Do not insert blank rows or notes below the data.
- Keep a private backup of this folder outside git; after untracking, these are the only copies.

## Removed

`ovi.xlsx` (EIZ business confidence index OVI) was removed on 2026-09-04 because the index is no longer published. It is not read by the Python pipeline. The R reference script `skripte/samo_hrvatska.R` still tries to read it and skips the indicator with a warning when the file is absent. The last tracked copy is in git history at commit 771c499 as `datasets/ovi.xlsx`.

## Note for the R fixture run (task 1.2)

The R scripts read these files by bare file name from the working directory and write their Excel outputs into that same directory. Run R from a scratch copy of this folder, never from `data/` itself.
