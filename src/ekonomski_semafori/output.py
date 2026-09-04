"""Write pipeline results for Flourish.

Inputs: the long panel from pipeline.run_all [country, indicator_id, time,
mom_z, cycle_z], plus the config registries and settings.
Outputs, under an output directory:
- all_countries_long.csv: one row per (indicator, category, country, month) from
  settings.output_start, columns time (ISO, first of month), label (Croatian
  month name and year), country, country_name, category, indicator_id,
  indicator_name_hr, indicator_name_en, mom_z, cycle_z (clipped at
  settings.axis_clip), clipped (true where a value was clipped).
- by_indicator/<indicator_id>.csv: filtered views of the master file.
- axis_bounds.csv: min and max of mom_z and cycle_z per (scope, category) where
  scope is a country code or ALL, plus per indicator across countries.
- Legacy Excel workbooks in the R layout, kept for one release cycle so the
  existing Flourish charts keep working: Business_Cycle_<Country>.xlsx with one
  sheet per category and a combined sheet; for Croatia the five category files
  and the combined file; Euro_Area_Business_Cycles_All_Countries.xlsx;
  Axis_Boundaries_Croatia.xlsx and Axis_Boundaries_Summary.xlsx.
Assumptions: CSV files are UTF-8 with BOM so Excel on Windows shows diacritics.
An indicator in two categories (GDP) appears once per category in the master
file and in the per-category legacy sheets, but once per month in the combined
legacy sheets, which Flourish keys on (time, Varijabla). Legacy time labels use English month names
(the R scripts were locale dependent; the fixtures were produced under LC_TIME C).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ekonomski_semafori.config import Country, Indicator, Settings

CATEGORY_SHEETS = {
    "leading": "1_vodeci_indikatori",
    "supply": "2_podudarni_proizvodnja",
    "demand": "3_podudarni_potrosnja_trgovina",
    "external": "4_vanjska_trgovina",
    "lagging": "5_kasni_indikatori_stecaj",
}
HR_MONTHS = ["siječanj", "veljača", "ožujak", "travanj", "svibanj", "lipanj",
             "srpanj", "kolovoz", "rujan", "listopad", "studeni", "prosinac"]
LEGACY_COLUMNS = {"mom_z": "Mjesečna promjena (%)", "cycle_z": "Odstupanje od trenda (%)", "indicator_name_hr": "Varijabla"}
MASTER_COLUMNS = ["time", "label", "country", "country_name", "category", "indicator_id",
                  "indicator_name_hr", "indicator_name_en", "mom_z", "cycle_z", "clipped"]


def build_long(panel: pd.DataFrame, countries: dict[str, Country], indicators: list[Indicator], settings: Settings) -> pd.DataFrame:
    """Attach names and categories to the panel, expand multi-category indicators,
    and keep months from settings.output_start."""
    by_id = {i.id: i for i in indicators}
    rows = panel[panel["time"] >= pd.Timestamp(settings.output_start)].copy()
    rows["category"] = rows["indicator_id"].map(lambda i: list(by_id[i].category))
    rows = rows.explode("category", ignore_index=True)
    rows["country_name"] = rows["country"].map(lambda c: countries[c].name_en)
    rows["indicator_name_hr"] = rows["indicator_id"].map(lambda i: by_id[i].name_hr)
    rows["indicator_name_en"] = rows["indicator_id"].map(lambda i: by_id[i].name_en)
    rows["label"] = [f"{HR_MONTHS[t.month - 1]} {t.year}" for t in rows["time"]]
    clip = settings.axis_clip
    rows["clipped"] = (rows["mom_z"].abs() > clip) | (rows["cycle_z"].abs() > clip)
    rows[["mom_z", "cycle_z"]] = rows[["mom_z", "cycle_z"]].clip(-clip, clip)
    order = {c: n for n, c in enumerate(CATEGORY_SHEETS)}
    rows["_cat"] = rows["category"].map(order)
    rows = rows.sort_values(["country", "_cat", "indicator_id", "time"], ignore_index=True).drop(columns="_cat")
    return rows[MASTER_COLUMNS]


def axis_bounds(long: pd.DataFrame) -> pd.DataFrame:
    """Rounded min and max of both axes per country and category, per category
    over all countries, and per indicator over all countries."""
    def bounds(frame: pd.DataFrame, scope_type: str, scope: str, category: str) -> dict:
        return {"scope_type": scope_type, "scope": scope, "category": category,
                "mom_min": frame["mom_z"].min(), "mom_max": frame["mom_z"].max(),
                "cycle_min": frame["cycle_z"].min(), "cycle_max": frame["cycle_z"].max()}
    out = []
    for (country, category), frame in long.groupby(["country", "category"], sort=True):
        out.append(bounds(frame, "country", country, category))
    for country, frame in long.groupby("country", sort=True):
        out.append(bounds(frame, "country", country, "ALL"))
    for category, frame in long.groupby("category", sort=True):
        out.append(bounds(frame, "all", "ALL", category))
    out.append(bounds(long, "all", "ALL", "ALL"))
    for indicator_id, frame in long.groupby("indicator_id", sort=True):
        out.append(bounds(frame, "indicator", indicator_id, "ALL"))
    return pd.DataFrame(out).round(3)


def write_csv_outputs(long: pd.DataFrame, out_dir: Path) -> None:
    """Master file, per-indicator views, and axis bounds, all UTF-8 with BOM."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "by_indicator").mkdir(exist_ok=True)
    long.to_csv(out_dir / "all_countries_long.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    for indicator_id, frame in long.groupby("indicator_id", sort=True):
        frame.to_csv(out_dir / "by_indicator" / f"{indicator_id}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    axis_bounds(long).to_csv(out_dir / "axis_bounds.csv", index=False, encoding="utf-8-sig")


def _legacy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[["time", "mom_z", "cycle_z", "indicator_name_hr"]].copy()
    out["time"] = out["time"].dt.strftime("%B %Y")
    out[["mom_z", "cycle_z"]] = out[["mom_z", "cycle_z"]].round(5)
    return out.rename(columns=LEGACY_COLUMNS)


def _legacy_bounds(frame: pd.DataFrame, name: str) -> dict:
    return {"Country": name, "MoM_Min": frame["mom_z"].min(), "MoM_Max": frame["mom_z"].max(),
            "Cycle_Min": frame["cycle_z"].min(), "Cycle_Max": frame["cycle_z"].max()}


def write_legacy_excel(long: pd.DataFrame, countries: dict[str, Country], out_dir: Path) -> None:
    """Workbooks in the layout the R scripts produced (see module docstring)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bounds = []
    combined_all = []
    for code, frame in long.groupby("country", sort=True):
        name = countries[code].name_en
        sheets = {sheet: _legacy_frame(frame[frame["category"] == cat]) for cat, sheet in CATEGORY_SHEETS.items() if (frame["category"] == cat).any()}
        # Flourish keys a series on (time, Varijabla): an indicator in two categories must appear once here.
        combined = _legacy_frame(frame.drop_duplicates(["time", "indicator_id"]))
        if code == "HR":
            for sheet, table in sheets.items():
                table.to_excel(out_dir / f"{sheet}.xlsx", index=False)
            combined.to_excel(out_dir / "combined_standardized_MoM_and_Cycle_Croatia.xlsx", index=False)
            pd.DataFrame([_legacy_bounds(frame, name)]).round(3).to_excel(out_dir / "Axis_Boundaries_Croatia.xlsx", index=False)
        else:
            with pd.ExcelWriter(out_dir / f"Business_Cycle_{name.replace(' ', '_')}.xlsx") as writer:
                for sheet, table in sheets.items():
                    table.to_excel(writer, sheet_name=sheet, index=False)
                combined.to_excel(writer, sheet_name="6_svi_indikatori", index=False)
            combined_all.append(combined.assign(Country=name)[["Country", *combined.columns]])
            bounds.append(_legacy_bounds(frame, name))
    if combined_all:
        pd.concat(combined_all, ignore_index=True).to_excel(out_dir / "Euro_Area_Business_Cycles_All_Countries.xlsx", index=False)
        others = long[long["country"] != "HR"]
        bounds.append(_legacy_bounds(others, "OVERALL (All Countries)"))
        pd.DataFrame(bounds).round(3).to_excel(out_dir / "Axis_Boundaries_Summary.xlsx", index=False)


def write_all(panel: pd.DataFrame, countries: dict[str, Country], indicators: list[Indicator], settings: Settings, out_dir: Path) -> pd.DataFrame:
    """Build the long panel and write every output; returns the long panel (clipped
    values). The unclipped panel is what run_monthly.py archives as a vintage."""
    long = build_long(panel, countries, indicators, settings)
    write_csv_outputs(long, out_dir)
    write_legacy_excel(long, countries, out_dir / "legacy")
    return long
