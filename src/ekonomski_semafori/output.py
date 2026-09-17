"""Write pipeline results: the analytical master file and the files the Flourish
scatter charts read.

Inputs: the long panel from pipeline.run_all [country, indicator_id, time,
mom_z, cycle_z], plus the config registries and settings.
Outputs, under an output directory:
- all_countries_long.csv: one row per (indicator, category, country, month) from
  settings.output_start, columns time (ISO, first of month), label (Croatian
  month name and year), country, country_name, category, panel (main,
  confirmation or financial), indicator_id, indicator_name_hr,
  indicator_name_en, mom_z, cycle_z (clipped at settings.axis_clip), clipped
  (true where a value was clipped).
- axis_bounds.csv: min and max of mom_z and cycle_z per (scope, category) where
  scope is a country code or ALL, plus per indicator across countries.
- Chart files, one per Flourish visualisation, in the chart layout (CHART_COLUMNS,
  Croatian headers, values rounded to 3 decimals, rows in calendar order):
  by_indicator/<indicator_id>.csv holds every country for one indicator (name =
  country, plus Skupina: Hrvatska or Ostale zemlje for the colour);
  by_country/<code>/6_svi_indikatori.csv holds every indicator for one country
  and by_country/<code>/<n>_<category>.csv one category, named like the sheets
  of the retired R workbooks. The first four columns are the time slider, x, y
  and name, so replacing a chart's data keeps its bindings.
Assumptions: CSV files are UTF-8 with BOM so Excel on Windows shows diacritics.
An indicator in two categories (GDP) appears once per category in the master
file and the category files, but once per month in the all-indicator and
per-indicator files (under supply), so a dot is never doubled.
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
CATEGORY_HR = {
    "leading": "Vodeći pokazatelji",
    "supply": "Podudarni: proizvodnja",
    "demand": "Podudarni: potrošnja i trgovina",
    "external": "Vanjska trgovina",
    "lagging": "Zaostajući pokazatelji",
}
CHART_COLUMNS = ["Mjesec", "Mjesečna promjena (z)", "Odstupanje od trenda (z)", "Varijabla", "Kategorija", "Datum"]
MASTER_COLUMNS = ["time", "label", "country", "country_name", "category", "panel", "indicator_id",
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
    rows["panel"] = rows["indicator_id"].map(lambda i: by_id[i].panel)
    rows["label"] = [f"{HR_MONTHS[t.month - 1]} {t.year}" for t in rows["time"]]
    clip = settings.axis_clip
    rows["clipped"] = (rows["mom_z"].abs() > clip) | (rows["cycle_z"].abs() > clip)
    rows[["mom_z", "cycle_z"]] = rows[["mom_z", "cycle_z"]].clip(-clip, clip)
    rows["_cat"] = rows["category"].map({c: n for n, c in enumerate(CATEGORY_SHEETS)})
    rows["_ind"] = rows["indicator_id"].map({i.id: n for n, i in enumerate(indicators)})   # registry order within a category
    rows = rows.sort_values(["country", "_cat", "_ind", "time"], ignore_index=True).drop(columns=["_cat", "_ind"])
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


def chart_frame(frame: pd.DataFrame, name: pd.Series, group: pd.Series | None = None) -> pd.DataFrame:
    """Rows of the master file in the chart layout: slider, x, y, name, category,
    ISO date, plus an optional colour group; sorted by month so a text time slider
    runs in calendar order."""
    out = pd.DataFrame({
        "Mjesec": frame["label"].to_numpy(),
        "Mjesečna promjena (z)": frame["mom_z"].round(3).to_numpy(),
        "Odstupanje od trenda (z)": frame["cycle_z"].round(3).to_numpy(),
        "Varijabla": name.to_numpy(),
        "Kategorija": frame["category"].map(CATEGORY_HR).to_numpy(),
        "Datum": frame["time"].dt.strftime("%Y-%m-%d").to_numpy(),
    })
    if group is not None:
        out["Skupina"] = group.to_numpy()
    return out.sort_values("Datum", kind="stable", ignore_index=True)


def write_csv_outputs(long: pd.DataFrame, countries: dict[str, Country], out_dir: Path) -> None:
    """Master file, axis bounds and the chart files, all UTF-8 with BOM."""
    csv = {"index": False, "encoding": "utf-8-sig", "date_format": "%Y-%m-%d"}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "by_indicator").mkdir(exist_ok=True)
    long.to_csv(out_dir / "all_countries_long.csv", **csv)
    axis_bounds(long).to_csv(out_dir / "axis_bounds.csv", index=False, encoding="utf-8-sig")
    once = long.drop_duplicates(["country", "indicator_id", "time"])   # one dot per month for GDP, listed under supply
    for indicator_id, frame in once.groupby("indicator_id", sort=False):
        group = frame["country"].eq("HR").map({True: "Hrvatska", False: "Ostale zemlje"})
        chart_frame(frame, frame["country"].map(lambda c: countries[c].name_hr), group).to_csv(out_dir / "by_indicator" / f"{indicator_id}.csv", **csv)
    for code, frame in long.groupby("country", sort=True):
        folder = out_dir / "by_country" / code
        folder.mkdir(parents=True, exist_ok=True)
        rows = once[once["country"] == code]
        chart_frame(rows, rows["indicator_name_hr"]).to_csv(folder / "6_svi_indikatori.csv", **csv)
        for category, sheet in CATEGORY_SHEETS.items():
            rows = frame[frame["category"] == category]
            if not rows.empty:
                chart_frame(rows, rows["indicator_name_hr"]).to_csv(folder / f"{sheet}.csv", **csv)


def write_all(panel: pd.DataFrame, countries: dict[str, Country], indicators: list[Indicator], settings: Settings, out_dir: Path) -> pd.DataFrame:
    """Build the long panel and write every output; returns the long panel (clipped
    values). The unclipped panel is what run_monthly.py archives as a vintage."""
    long = build_long(panel, countries, indicators, settings)
    write_csv_outputs(long, countries, out_dir)
    return long
