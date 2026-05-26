"""Parsers voor DUO MBO bestandsformaten naar genormaliseerde Polars DataFrames.

Ondersteunde formaten:
- H15 Registratie Overzicht (RO): pipe- of puntkomma-gescheiden records
- H16 TBG-i (TBGI): XML
- H17 Afslag register-levering IP (GRONDSLAG_IP): puntkomma-gescheiden records
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

_SCHEMA: dict[str, pl.DataType] = {
    "bsn": pl.String,
    "brin": pl.String,
    "geslacht": pl.String,
    "heeft_diploma": pl.Boolean,
    "inschrijving_start": pl.String,
    "inschrijving_eind": pl.String,
    "uitschrijving_reden": pl.String,
    "leertraject": pl.String,
    "opleidingscode": pl.String,
    "vorig_onderwijs_niveau": pl.String,
    "vorig_onderwijs_graad": pl.String,
    "geboortedatum": pl.String,
    "leeftijd": pl.Int64,
}


def parse_ro(path: str | Path) -> pl.DataFrame:
    """Parse H15 Registratie Overzicht naar student DataFrame.

    Ondersteunt zowel pipe-delimited (Aventus) als semicolon-delimited (Curio) varianten.
    BRIN wordt uit de VLP-header gehaald; als die ontbreekt, uit de bestandsnaam.
    """
    path = Path(path)
    brin_fallback = path.stem.split("_")[1] if "_" in path.stem else None
    return _parse_ro_records(path, brin_fallback=brin_fallback)


def parse_tbgi(path: str | Path) -> pl.DataFrame:
    """Parse H16 TBG-i XML naar student DataFrame."""
    from lxml import etree

    root = etree.parse(str(path)).getroot()
    records = [_extract_tbgi_inschrijving(el) for el in root.findall("Inschrijving")]
    return _to_dataframe(records, date_format_start="iso", date_format_eind="iso")


def parse_grondslag_ip(path: str | Path) -> pl.DataFrame:
    """Parse H17 Afslag register-levering IP (semicolon-delimited) naar student DataFrame.

    BRIN staat in ISG-records (positie [2]), geslacht in PER-records op positie [6].
    Datumformaat: yyyyMMdd.
    """
    students: dict[str, dict[str, Any]] = {}

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split(";")
            record_type = parts[0]

            if record_type == "PER":
                bsn = parts[1] or (parts[2] if len(parts) > 2 else "")
                if not bsn:
                    continue
                students[bsn] = _init_student_record(
                    bsn, brin=None, geslacht=parts[6] if len(parts) > 6 else None
                )
                raw_leeftijd = parts[2] if len(parts) > 2 else None
                students[bsn]["leeftijd"] = (
                    int(raw_leeftijd) if raw_leeftijd and raw_leeftijd.isdigit() else None
                )

            elif record_type == "ISG" and parts[1] in students:
                s = students[parts[1]]
                s["brin"] = parts[2] if len(parts) > 2 else None
                s["inschrijving_start"] = parts[4] if len(parts) > 4 else None
                s["inschrijving_eind"] = parts[5] if len(parts) > 5 else None
                s["uitschrijving_reden"] = parts[7] if len(parts) > 7 else None

            elif record_type == "ISP" and parts[1] in students:
                s = students[parts[1]]
                s["opleidingscode"] = parts[6] if len(parts) > 6 else None
                s["leertraject"] = parts[8] if len(parts) > 8 else None

            elif record_type == "DIP" and parts[1] in students:
                students[parts[1]]["heeft_diploma"] = True

            elif record_type == "GEO" and parts[1] in students:
                _update_geo(students[parts[1]], parts, niveau_pos=7, graad_pos=6)

    return _to_dataframe(
        list(students.values()),
        date_format_start="%Y%m%d",
        date_format_eind="%Y%m%d",
    )


def _parse_ro_records(path: Path, brin_fallback: str | None) -> pl.DataFrame:
    """Parser voor H15 RO record-structuur; detecteert scheidingsteken uit eerste regel."""
    students: dict[str, dict[str, Any]] = {}
    brin = brin_fallback
    sep: str | None = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if sep is None:
                sep = "|" if "|" in stripped else ";"
            parts = stripped.split(sep)
            record_type = parts[0]

            if record_type == "VLP":
                brin = parts[1] if len(parts) > 1 else brin_fallback

            elif record_type == "PER":
                bsn = parts[1] or (parts[2] if len(parts) > 2 else "")
                if not bsn:
                    continue
                students[bsn] = _init_student_record(
                    bsn, brin=brin, geslacht=parts[4] if len(parts) > 4 else None
                )
                students[bsn]["geboortedatum"] = parts[3] if len(parts) > 3 else None

            elif record_type == "ISG" and parts[1] in students:
                s = students[parts[1]]
                s["inschrijving_start"] = parts[4] if len(parts) > 4 else None
                s["inschrijving_eind"] = parts[5] if len(parts) > 5 else None
                s["uitschrijving_reden"] = parts[7] if len(parts) > 7 else None

            elif record_type == "ISP" and parts[1] in students:
                s = students[parts[1]]
                s["opleidingscode"] = parts[5] if len(parts) > 5 else None
                s["leertraject"] = parts[7] if len(parts) > 7 else None

            elif record_type == "DIP" and parts[1] in students:
                students[parts[1]]["heeft_diploma"] = True

            elif record_type == "GEO" and parts[1] in students:
                _update_geo(students[parts[1]], parts, niveau_pos=8, graad_pos=7)

    # H15 heeft gemixte datumformaten — probeer ISO dan Europees
    return _to_dataframe(
        list(students.values()),
        date_format_start=None,
        date_format_eind=None,
    )


def _init_student_record(bsn: str, brin: str | None, geslacht: str | None) -> dict[str, Any]:
    return {
        "bsn": bsn,
        "brin": brin,
        "geslacht": geslacht,
        "heeft_diploma": False,
        "inschrijving_start": None,
        "inschrijving_eind": None,
        "uitschrijving_reden": None,
        "leertraject": None,
        "opleidingscode": None,
        "vorig_onderwijs_niveau": None,
        "vorig_onderwijs_graad": None,
        "geboortedatum": None,
        "leeftijd": None,
    }


def _update_geo(
    student: dict[str, Any], parts: list[str], niveau_pos: int, graad_pos: int
) -> None:
    """Vul vooropleidingsvelden uit GEO-record; overschrijft niet als al aanwezig."""
    if student["vorig_onderwijs_niveau"] is None:
        student["vorig_onderwijs_niveau"] = parts[niveau_pos] if len(parts) > niveau_pos else None
        student["vorig_onderwijs_graad"] = parts[graad_pos] if len(parts) > graad_pos else None


def _extract_tbgi_inschrijving(node: Any) -> dict[str, Any]:
    """Extraheer genormaliseerde velden uit een TBG-i <Inschrijving> XML-element.

    nil-attributen (xsi:nil='true') worden als None behandeld.
    """

    def text(tag: str) -> str | None:
        el = node.find(tag)
        if el is None:
            return None
        return None if el.get(f"{{{_XSI_NS}}}nil") == "true" else el.text

    teldatum = node.find("Teldatum")
    raw_leeftijd = (
        teldatum.findtext("LeeftijdOpEenAugustusStudiejaar") if teldatum is not None else None
    )

    return {
        "bsn": text("Burgerservicenummer"),
        "brin": text("BRIN"),
        "geslacht": None,
        "inschrijving_start": text("DatumInschrijving"),
        "inschrijving_eind": text("DatumUitschrijvingGepland"),
        "uitschrijving_reden": text("DatumUitschrijvingWerkelijk"),
        "leertraject": teldatum.findtext("Leertraject") if teldatum is not None else None,
        "opleidingscode": teldatum.findtext("Opleidingcode") if teldatum is not None else None,
        "heeft_diploma": node.find("Diploma") is not None,
        "vorig_onderwijs_niveau": None,
        "vorig_onderwijs_graad": None,
        "geboortedatum": None,
        "leeftijd": int(raw_leeftijd) if raw_leeftijd and raw_leeftijd.isdigit() else None,
    }


def _parse_date_col(
    df: pl.DataFrame, col: str, fmt: str | None
) -> pl.DataFrame:
    """Cast een string-datumkolom naar pl.Date, ondersteunt mixed H15-formaten."""
    if col not in df.schema:
        return df
    # Kolom is volledig null (geen strings) — direct casten naar Date
    if df.schema[col] == pl.Null:
        return df.with_columns(pl.col(col).cast(pl.Date))
    if fmt == "iso":
        return df.with_columns(pl.col(col).str.to_date(format="%Y-%m-%d", strict=False))
    if fmt is not None:
        return df.with_columns(pl.col(col).str.to_date(format=fmt, strict=False))
    # Gemixte H15-datums: probeer ISO, dan Europees (dd-MM-yyyy)
    return df.with_columns(
        pl.col(col)
        .str.to_date(format="%Y-%m-%d", strict=False)
        .fill_null(pl.col(col).str.to_date(format="%d-%m-%Y", strict=False))
    )


def _to_dataframe(
    records: list[dict[str, Any]],
    date_format_start: str | None,
    date_format_eind: str | None,
) -> pl.DataFrame:
    """Zet lijst van student-dicts om naar getypeerd Polars DataFrame."""
    if not records:
        return pl.DataFrame(schema=_SCHEMA)

    df = pl.DataFrame(records, schema_overrides={"leeftijd": pl.Int64})
    df = _parse_date_col(df, "inschrijving_start", date_format_start)
    df = _parse_date_col(df, "inschrijving_eind", date_format_eind)

    if "geboortedatum" in df.schema:
        df = _parse_date_col(df, "geboortedatum", None)

    if "vorig_onderwijs_graad" in df.schema:
        df = df.with_columns(
            pl.col("vorig_onderwijs_graad").cast(pl.Int64, strict=False)
        )

    return df
