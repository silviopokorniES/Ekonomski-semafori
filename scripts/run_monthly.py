"""Monthly production run: fetch everything, compute, write outputs, keep a vintage.

Usage (inside the semafori conda environment, from the repository root):
    python scripts/run_monthly.py [--output DIR]

Outputs under DIR (default output/): all_countries_long.csv, by_indicator/,
axis_bounds.csv, legacy/ (see output.py), logs/<date>.log,
Processing_Summary.csv (country, indicators processed, first and last published
month, indicators skipped with the first line of each reason, and the pairs that
ran without their frozen model or Henderson trend), and vintages/<date>.csv, an archive of the unclipped
panel for revision analysis. Any infrastructure failure raises and the process exits
non-zero; data skips are listed in the log and in the summary.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ekonomski_semafori.config import load_countries, load_indicators, load_settings  # noqa: E402
from ekonomski_semafori.output import write_all  # noqa: E402
from ekonomski_semafori.pipeline import run_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ekonomski semafori monthly run")
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    today = date.today().isoformat()
    (args.output / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(args.output / "logs" / f"{today}.log", encoding="utf-8"), logging.StreamHandler()],
    )
    countries, indicators, settings = load_countries(), load_indicators(), load_settings()
    skips: list[tuple[str, str, str]] = []
    notes: list[tuple[str, str, str]] = []
    panel = run_all(countries, indicators, settings, skips=skips, notes=notes)
    long = write_all(panel, countries, indicators, settings, args.output)
    (args.output / "vintages").mkdir(exist_ok=True)
    panel.to_csv(args.output / "vintages" / f"{today}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    summary = (
        long.groupby("country")
        .agg(indicators_processed=("indicator_id", "nunique"), first_month=("time", "min"), last_month=("time", "max"))
        .reindex(list(countries))
        .rename_axis("country")
        .reset_index()
    )
    summary["indicators_processed"] = summary["indicators_processed"].fillna(0).astype(int)
    summary["indicators_skipped"] = summary["country"].map(lambda c: sum(1 for s in skips if s[0] == c))
    summary["skipped_ids"] = summary["country"].map(lambda c: "; ".join(f"{s[1]} ({s[2].splitlines()[0]})" for s in skips if s[0] == c))
    summary["fallbacks"] = summary["country"].map(lambda c: "; ".join(f"{n[1]} ({n[2]})" for n in notes if n[0] == c))
    summary.to_csv(args.output / "Processing_Summary.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    logging.info("run complete: %d pairs, %d skipped, outputs in %s", panel.groupby(["country", "indicator_id"]).ngroups, len(skips), args.output)


if __name__ == "__main__":
    main()
