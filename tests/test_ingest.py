"""Tests voor de ingest-parsers met demo-data."""

from pathlib import Path

import polars as pl
import pytest

from eencijfermbo.core.ingest import parse_grondslag_ip, parse_ro, parse_tbgi

DEMO = Path(__file__).parent.parent / "data" / "01-raw" / "demo"
H15_DIR = DEMO / "h15"
H16_DIR = DEMO / "h16"
H17_DIR = DEMO / "h17"

VERWACHTE_KOLOMMEN = {
    "bsn", "brin", "geslacht", "heeft_diploma",
    "inschrijving_start", "inschrijving_eind", "uitschrijving_reden",
    "uitschrijving_datum", "leertraject", "opleidingscode",
    "vorig_onderwijs_niveau", "vorig_onderwijs_graad", "geboortedatum", "leeftijd",
    "niveau_mbo", "diploma_datum", "diploma_crebo",
    "bpv_stages_aantal", "bpv_uren_totaal", "kzd_behaald_aantal",
}


def _h15_bestanden() -> list[Path]:
    return list(H15_DIR.glob("*.csv")) + list(H15_DIR.glob("*.txt"))


def _h16_bestanden() -> list[Path]:
    return list(H16_DIR.glob("*.xml")) + list(H16_DIR.glob("*.XML"))


def _h17_bestanden() -> list[Path]:
    return list(H17_DIR.glob("*.csv")) + list(H17_DIR.glob("*.txt"))


@pytest.mark.skipif(not H15_DIR.exists(), reason="Geen H15 demo-data")
@pytest.mark.parametrize("pad", _h15_bestanden())
def test_parse_ro(pad: Path) -> None:
    df = parse_ro(pad)
    assert isinstance(df, pl.DataFrame)
    assert len(df) > 0
    assert VERWACHTE_KOLOMMEN.issubset(set(df.columns))
    assert df["brin"].is_not_null().any(), f"brin is null voor {pad.name}"


@pytest.mark.skipif(not H15_DIR.exists(), reason="Geen H15 demo-data")
@pytest.mark.parametrize("pad", _h15_bestanden())
def test_parse_ro_bpv(pad: Path) -> None:
    df = parse_ro(pad)
    assert "bpv_stages_aantal" in df.columns
    assert df["bpv_stages_aantal"].sum() > 0, f"Geen BPV-records geparsed in {pad.name}"


@pytest.mark.skipif(not H16_DIR.exists(), reason="Geen H16 demo-data")
@pytest.mark.parametrize("pad", _h16_bestanden())
def test_parse_tbgi(pad: Path) -> None:
    df = parse_tbgi(pad)
    assert isinstance(df, pl.DataFrame)
    assert len(df) > 0
    assert VERWACHTE_KOLOMMEN.issubset(set(df.columns))
    assert "niveau_mbo" in df.columns
    assert "verblijfsjaar_mbo" in df.columns


@pytest.mark.skipif(not H17_DIR.exists(), reason="Geen H17 demo-data")
@pytest.mark.parametrize("pad", _h17_bestanden())
def test_parse_grondslag_ip(pad: Path) -> None:
    df = parse_grondslag_ip(pad)
    assert isinstance(df, pl.DataFrame)
    assert len(df) > 0
    assert VERWACHTE_KOLOMMEN.issubset(set(df.columns))
    assert df["brin"].is_not_null().any(), "brin is null in H17"


@pytest.mark.skipif(not H17_DIR.exists(), reason="Geen H17 demo-data")
@pytest.mark.parametrize("pad", _h17_bestanden())
def test_parse_grondslag_ip_postcode(pad: Path) -> None:
    df = parse_grondslag_ip(pad)
    assert "postcode" in df.columns
    assert df["postcode"].is_not_null().any(), "Geen postcodes geparsed uit H17"


def test_parse_ro_lege_dataframe_als_geen_data(tmp_path: Path) -> None:
    leeg = tmp_path / "RO_TEST_20240101_20241231.csv"
    leeg.write_text("")
    df = parse_ro(leeg)
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 0
