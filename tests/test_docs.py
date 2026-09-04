"""The methodology document must agree with the indicator registry. The Croatian
version is kept locally, not published, and is checked when present."""

from pathlib import Path

from ekonomski_semafori.config import load_indicators, load_settings

ROOT = Path(__file__).resolve().parents[1]
DOCS = [p for p in ("business_cycle_methodology.md", "metodologija.md") if (ROOT / p).exists()]


def test_every_indicator_is_documented_in_both_languages() -> None:
    english = (ROOT / "business_cycle_methodology.md").read_text(encoding="utf-8")
    croatian = (ROOT / "metodologija.md").read_text(encoding="utf-8") if "metodologija.md" in DOCS else None
    for indicator in load_indicators():
        assert indicator.name_en in english, indicator.id
        if croatian is not None:
            assert indicator.name_hr in croatian, indicator.id
        assert (indicator.dataset or indicator.series_key.split(".")[0]) in english if indicator.source != "local" else True, indicator.id


def test_documents_state_the_settings_in_force() -> None:
    settings = load_settings()
    for path in DOCS:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "129" in text and "600" in text, path                      # lambda
        assert str(settings.zscore_min_obs) in text, path
        assert str(settings.zscore_window.year) in text, path
        assert "—" not in text and "–" not in text, path         # no em or en dashes
