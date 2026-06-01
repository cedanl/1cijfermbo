"""Parsers voor DUO MBO bestandsformaten naar genormaliseerde Polars DataFrames.

Ondersteunde formaten:
- H15 Registratie Overzicht (RO): pipe- of puntkomma-gescheiden records
- H16 TBG-i (TBGI): XML
- H17 Afslag register-levering IP (GRONDSLAG_IP): puntkomma-gescheiden records

Alle beschikbare velden worden geparsed. Meerdere ISP-records per student:
meest recente op basis van startdatum wordt bewaard. BPV- en KZD-records
worden geaggregeerd per student.
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
    "geboortedatum": pl.Date,
    "leeftijd": pl.Int64,
    "postcode": pl.String,
    "nationaliteitscode": pl.String,
    "nationaliteit_2": pl.String,
    "geboorteland": pl.String,
    "geboorteland_ouder_1": pl.String,
    "geboorteland_ouder_2": pl.String,
    "inschrijving_start": pl.Date,
    "inschrijving_eind": pl.Date,
    "uitschrijving_datum": pl.Date,
    "uitschrijving_reden": pl.String,
    "opleidingscode": pl.String,
    "leertraject": pl.String,
    "niveau_mbo": pl.String,
    "kwalificatiedossier": pl.String,
    "crebo_kwalificatie": pl.String,
    "bekostigd": pl.String,
    "heeft_diploma": pl.Boolean,
    "diploma_datum": pl.Date,
    "diploma_crebo": pl.String,
    "vorig_onderwijs_niveau": pl.String,
    "vorig_onderwijs_graad": pl.Int64,
    "verblijfsjaar_mbo": pl.Int64,
    "bekostigingsstatus": pl.Boolean,
    "bpv_stages_aantal": pl.Int64,
    "bpv_uren_totaal": pl.Int64,
    "bpv_leerbedrijf_id": pl.String,
    "kzd_behaald_aantal": pl.Int64,
    "kzd_codes": pl.String,
}


def parse_ro(path: str | Path) -> pl.DataFrame:
    """Parse H15 Registratie Overzicht naar student DataFrame.

    Ondersteunt pipe- en puntkomma-gescheiden varianten.
    BRIN uit VLP-header (ook als die onderaan staat); valt terug op bestandsnaam.
    """
    path = Path(path)
    return _parse_ro_records(path, brin_fallback=_brin_uit_bestandsnaam(path))


def parse_tbgi(path: str | Path) -> pl.DataFrame:
    """Parse H16 TBG-i XML naar student DataFrame."""
    from lxml import etree

    root = etree.parse(str(path)).getroot()
    records = [_extract_tbgi_inschrijving(el) for el in root.findall("Inschrijving")]
    for el in root.findall("Diploma"):
        _merge_tbgi_diploma(el, records)
    return _to_dataframe(records, h15_dates=False)


def parse_grondslag_ip(path: str | Path) -> pl.DataFrame:
    """Parse H17 Afslag register-levering IP naar student DataFrame."""
    students: dict[str, dict[str, Any]] = {}
    brin_uit_vlp: str | None = None
    brin_fallback = _brin_uit_bestandsnaam(Path(path))

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split(";")
            rt = parts[0]

            if rt == "VLP":
                brin_uit_vlp = _nonempty(_get(parts, 1))

            elif rt == "PER":
                bsn = _nonempty(_get(parts, 1))
                if not bsn:
                    continue
                students[bsn] = _init_student_record(bsn, brin=None, geslacht=_get(parts, 6))
                students[bsn]["leeftijd"] = _int(_get(parts, 2))
                students[bsn]["postcode"] = _nonempty(_get(parts, 7))
                students[bsn]["geboorteland"] = _nonempty(_get(parts, 11))
                students[bsn]["geboorteland_ouder_1"] = _nonempty(_get(parts, 12))
                students[bsn]["geboorteland_ouder_2"] = _nonempty(_get(parts, 13))
                students[bsn]["nationaliteitscode"] = _nonempty(_get(parts, 16))
                students[bsn]["nationaliteit_2"] = _nonempty(_get(parts, 17))

            elif rt == "ISG" and _get(parts, 1) in students:
                s = students[parts[1]]
                s["brin"] = _nonempty(_get(parts, 2)) or brin_uit_vlp or brin_fallback
                s["inschrijving_start"] = _nonempty(_get(parts, 4))
                s["inschrijving_eind"] = _nonempty(_get(parts, 5))
                s["uitschrijving_datum"] = _nonempty(_get(parts, 6))
                s["uitschrijving_reden"] = _nonempty(_get(parts, 7))

            elif rt == "ISP" and _get(parts, 1) in students:
                _update_isp_h17(students[parts[1]], parts)

            elif rt == "BPV" and _get(parts, 1) in students:
                _update_bpv(students[parts[1]], parts, uren_pos=9, leerbedrijf_pos=10)

            elif rt == "DIP" and _get(parts, 1) in students:
                s = students[parts[1]]
                s["heeft_diploma"] = True
                s["diploma_datum"] = _nonempty(_get(parts, 5))
                s["diploma_crebo"] = _nonempty(_get(parts, 4))

            elif rt == "GEO" and _get(parts, 1) in students:
                _update_geo_h17(students[parts[1]], parts)

            elif rt == "KZD" and _get(parts, 1) in students:
                _update_kzd(students[parts[1]], parts, code_pos=5, status_pos=6)

    brin_definitief = brin_uit_vlp or brin_fallback
    for s in students.values():
        if not s["brin"]:
            s["brin"] = brin_definitief

    return _to_dataframe(list(students.values()), h15_dates=False)


def _parse_ro_records(path: Path, brin_fallback: str | None) -> pl.DataFrame:
    students: dict[str, dict[str, Any]] = {}
    brin_uit_vlp: str | None = None
    sep: str | None = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if sep is None:
                sep = "|" if "|" in stripped else ";"
            parts = stripped.split(sep)
            rt = parts[0]

            if rt == "VLP":
                brin_uit_vlp = _nonempty(_get(parts, 1))

            elif rt == "PER":
                bsn = _nonempty(_get(parts, 1)) or _nonempty(_get(parts, 2))
                if not bsn:
                    continue
                students[bsn] = _init_student_record(
                    bsn,
                    brin=brin_uit_vlp or brin_fallback,
                    geslacht=_get(parts, 4),
                )
                students[bsn]["geboortedatum"] = _nonempty(_get(parts, 3))

            elif rt == "ISG" and _get(parts, 1) in students:
                s = students[parts[1]]
                s["inschrijving_start"] = _nonempty(_get(parts, 4))
                s["inschrijving_eind"] = _nonempty(_get(parts, 5))
                s["uitschrijving_datum"] = _nonempty(_get(parts, 6))
                s["uitschrijving_reden"] = _nonempty(_get(parts, 7))

            elif rt == "ISP" and _get(parts, 1) in students:
                _update_isp_h15(students[parts[1]], parts)

            elif rt == "BPV" and _get(parts, 1) in students:
                _update_bpv(students[parts[1]], parts, uren_pos=9, leerbedrijf_pos=10)

            elif rt == "DIP" and _get(parts, 1) in students:
                s = students[parts[1]]
                s["heeft_diploma"] = True
                s["diploma_datum"] = _nonempty(_get(parts, 5))
                s["diploma_crebo"] = _nonempty(_get(parts, 4))

            elif rt == "GEO" and _get(parts, 1) in students:
                _update_geo_h15(students[parts[1]], parts)

            elif rt == "KZD" and _get(parts, 1) in students:
                _update_kzd(students[parts[1]], parts, code_pos=6, status_pos=8)

    brin_definitief = brin_uit_vlp or brin_fallback
    for s in students.values():
        if not s["brin"]:
            s["brin"] = brin_definitief

    return _to_dataframe(list(students.values()), h15_dates=True)


def _init_student_record(bsn: str, brin: str | None, geslacht: str | None) -> dict[str, Any]:
    return {
        "bsn": bsn,
        "brin": brin,
        "geslacht": _nonempty(geslacht),
        "geboortedatum": None,
        "leeftijd": None,
        "postcode": None,
        "nationaliteitscode": None,
        "nationaliteit_2": None,
        "geboorteland": None,
        "geboorteland_ouder_1": None,
        "geboorteland_ouder_2": None,
        "inschrijving_start": None,
        "inschrijving_eind": None,
        "uitschrijving_datum": None,
        "uitschrijving_reden": None,
        "opleidingscode": None,
        "leertraject": None,
        "niveau_mbo": None,
        "kwalificatiedossier": None,
        "crebo_kwalificatie": None,
        "bekostigd": None,
        "heeft_diploma": False,
        "diploma_datum": None,
        "diploma_crebo": None,
        "vorig_onderwijs_niveau": None,
        "vorig_onderwijs_graad": None,
        "verblijfsjaar_mbo": None,
        "bekostigingsstatus": None,
        "bpv_stages_aantal": 0,
        "bpv_uren_totaal": 0,
        "bpv_leerbedrijf_id": None,
        "kzd_behaald_aantal": 0,
        "kzd_codes": None,
        "_isp_start": None,
        "_kzd_list": [],
    }


def _update_isp_h15(s: dict[str, Any], parts: list[str]) -> None:
    """Werk opleidingsvelden bij vanuit H15 ISP; behoudt meest recente startdatum."""
    # [1]=bsn, [3]=volgnummer, [4]=start, [5]=crebo, [6]=leertraject,
    # [8]=bekostigd(J/N), [10]=crebo_kwalificatie, [11]=kwalificatiedossier
    start = _nonempty(_get(parts, 4))
    if s["_isp_start"] is not None and start is not None and start <= s["_isp_start"]:
        return
    s["_isp_start"] = start
    s["opleidingscode"] = _nonempty(_get(parts, 5))
    s["leertraject"] = _nonempty(_get(parts, 6))
    s["bekostigd"] = _nonempty(_get(parts, 8))
    s["crebo_kwalificatie"] = _nonempty(_get(parts, 10))
    s["kwalificatiedossier"] = _nonempty(_get(parts, 11))


def _update_isp_h17(s: dict[str, Any], parts: list[str]) -> None:
    """Werk opleidingsvelden bij vanuit H17 ISP; behoudt meest recente startdatum."""
    # [1]=bsn, [2]=brin, [3]=volgnummer, [4]=start, [5]=eind, [6]=crebo,
    # [7]=niveau_tekst("MBO-4"), [8]=leertraject, [10]=niveau_num(1-4),
    # [11]=crebo_kwalificatie, [12]=kwalificatiedossier
    start = _nonempty(_get(parts, 4))
    if s["_isp_start"] is not None and start is not None and start <= s["_isp_start"]:
        return
    s["_isp_start"] = start
    s["opleidingscode"] = _nonempty(_get(parts, 6))
    niveau_tekst = _nonempty(_get(parts, 7))
    niveau_num = _nonempty(_get(parts, 10))
    s["niveau_mbo"] = niveau_tekst or (f"MBO-{niveau_num}" if niveau_num else None)
    s["leertraject"] = _nonempty(_get(parts, 8))
    s["crebo_kwalificatie"] = _nonempty(_get(parts, 11))
    s["kwalificatiedossier"] = _nonempty(_get(parts, 12))


def _update_bpv(s: dict[str, Any], parts: list[str], uren_pos: int, leerbedrijf_pos: int) -> None:
    s["bpv_stages_aantal"] += 1
    uren = _int(_get(parts, uren_pos))
    if uren:
        s["bpv_uren_totaal"] += uren
    leerbedrijf = _nonempty(_get(parts, leerbedrijf_pos))
    if leerbedrijf:
        s["bpv_leerbedrijf_id"] = leerbedrijf


def _update_geo_h15(s: dict[str, Any], parts: list[str]) -> None:
    """Vul vooropleidingsvelden uit H15 GEO type 3005 (VO diploma)."""
    # [6]=geo_type, [8]=vorig_niveau, [9]=cijfer_raw
    if s["vorig_onderwijs_niveau"] is not None:
        return
    if _nonempty(_get(parts, 6)) not in ("3005",):
        return
    s["vorig_onderwijs_niveau"] = _nonempty(_get(parts, 8))
    s["vorig_onderwijs_graad"] = _int(_get(parts, 9))


def _update_geo_h17(s: dict[str, Any], parts: list[str]) -> None:
    """Vul vooropleidingsvelden uit H17 GEO type 3001/3005."""
    # [5]=geo_type, [8]=cijfer1
    if s["vorig_onderwijs_graad"] is not None:
        return
    if _nonempty(_get(parts, 5)) not in ("3001", "3005"):
        return
    s["vorig_onderwijs_graad"] = _int(_get(parts, 8))


def _update_kzd(s: dict[str, Any], parts: list[str], code_pos: int, status_pos: int) -> None:
    code = _nonempty(_get(parts, code_pos))
    status = (_get(parts, status_pos) or "").upper()
    if "BEHAALD" in status and "NIET" not in status:
        s["kzd_behaald_aantal"] += 1
    if code:
        s["_kzd_list"].append(code)


def _extract_tbgi_inschrijving(node: Any) -> dict[str, Any]:
    """Extraheer alle velden uit een TBG-i <Inschrijving> XML-element."""

    def text(tag: str) -> str | None:
        el = node.find(tag)
        if el is None:
            return None
        return None if el.get(f"{{{_XSI_NS}}}nil") == "true" else (el.text or None)

    def ttext(tag: str) -> str | None:
        td = node.find("Teldatum")
        if td is None:
            return None
        el = td.find(tag)
        if el is None:
            return None
        return None if el.get(f"{{{_XSI_NS}}}nil") == "true" else (el.text or None)

    raw_leeftijd = ttext("LeeftijdOpEenAugustusStudiejaar")
    raw_verblijfsjaar = ttext("AantalBekostigdeVerblijfsjarenMBO")
    raw_bekostigd = ttext("IndicatieBekostigbaar")
    raw_bekostigingsstatus = ttext("Bekostigingsstatus")

    return {
        "bsn": text("Burgerservicenummer"),
        "brin": text("BRIN"),
        "geslacht": None,
        "geboortedatum": None,
        "leeftijd": int(raw_leeftijd) if raw_leeftijd and raw_leeftijd.isdigit() else None,
        "postcode": None,
        "nationaliteitscode": None,
        "nationaliteit_2": None,
        "geboorteland": None,
        "geboorteland_ouder_1": None,
        "geboorteland_ouder_2": None,
        "inschrijving_start": text("DatumInschrijving"),
        "inschrijving_eind": text("DatumUitschrijvingGepland"),
        "uitschrijving_datum": text("DatumUitschrijvingWerkelijk"),
        "uitschrijving_reden": None,
        "opleidingscode": ttext("Opleidingcode"),
        "leertraject": ttext("Leertraject"),
        "niveau_mbo": ttext("Niveau"),
        "kwalificatiedossier": None,
        "crebo_kwalificatie": None,
        "bekostigd": raw_bekostigd,
        "heeft_diploma": False,
        "diploma_datum": None,
        "diploma_crebo": None,
        "vorig_onderwijs_niveau": None,
        "vorig_onderwijs_graad": None,
        "verblijfsjaar_mbo": int(raw_verblijfsjaar)
        if raw_verblijfsjaar and raw_verblijfsjaar.isdigit()
        else None,
        "bekostigingsstatus": (raw_bekostigingsstatus == "true")
        if raw_bekostigingsstatus
        else None,
        "bpv_stages_aantal": 0,
        "bpv_uren_totaal": 0,
        "bpv_leerbedrijf_id": None,
        "kzd_behaald_aantal": 0,
        "kzd_codes": None,
        "_isp_start": None,
        "_kzd_list": [],
    }


def _merge_tbgi_diploma(node: Any, records: list[dict[str, Any]]) -> None:
    """Voeg diplomainfo uit H16 <Diploma> toe aan bijbehorend inschrijving-record."""

    def text(tag: str) -> str | None:
        el = node.find(tag)
        if el is None:
            return None
        return None if el.get(f"{{{_XSI_NS}}}nil") == "true" else (el.text or None)

    bsn = text("Burgerservicenummer")
    if not bsn:
        return
    for r in records:
        if r["bsn"] == bsn:
            r["heeft_diploma"] = True
            r["diploma_datum"] = text("DatumBehaald")
            r["diploma_crebo"] = text("Opleidingcode")
            break


def _to_dataframe(records: list[dict[str, Any]], *, h15_dates: bool) -> pl.DataFrame:
    for r in records:
        if r["_kzd_list"]:
            r["kzd_codes"] = ",".join(r["_kzd_list"])
        del r["_isp_start"]
        del r["_kzd_list"]

    if not records:
        return pl.DataFrame(schema=_SCHEMA)

    df = pl.DataFrame(
        records,
        schema_overrides={
            "leeftijd": pl.Int64,
            "vorig_onderwijs_graad": pl.Int64,
            "verblijfsjaar_mbo": pl.Int64,
            "bpv_stages_aantal": pl.Int64,
            "bpv_uren_totaal": pl.Int64,
            "kzd_behaald_aantal": pl.Int64,
        },
    )

    date_cols = [
        "inschrijving_start",
        "inschrijving_eind",
        "uitschrijving_datum",
        "diploma_datum",
        "geboortedatum",
    ]
    for col in date_cols:
        if col in df.schema:
            df = _parse_date_col(df, col, mixed=h15_dates)

    return df


def _parse_date_col(df: pl.DataFrame, col: str, *, mixed: bool) -> pl.DataFrame:
    if col not in df.schema:
        return df
    if df.schema[col] == pl.Null:
        return df.with_columns(pl.col(col).cast(pl.Date))
    if mixed:
        return df.with_columns(
            pl.col(col)
            .str.to_date(format="%Y-%m-%d", strict=False)
            .fill_null(pl.col(col).str.to_date(format="%d-%m-%Y", strict=False))
            .fill_null(pl.col(col).str.to_date(format="%-d-%-m-%Y", strict=False))
        )
    return df.with_columns(
        pl.col(col)
        .str.to_date(format="%Y-%m-%d", strict=False)
        .fill_null(pl.col(col).str.to_date(format="%Y%m%d", strict=False))
    )


def _get(parts: list[str], pos: int) -> str:
    return parts[pos] if len(parts) > pos else ""


def _nonempty(val: str | None) -> str | None:
    return val if val and val.strip() else None


def _int(val: str | None) -> int | None:
    if val and val.strip().lstrip("-").isdigit():
        return int(val.strip())
    return None


def _brin_uit_bestandsnaam(path: Path) -> str | None:
    """Extraheer BRIN-code (4 tekens: 2 cijfers + 2 letters) uit bestandsnaam."""
    for part in path.stem.split("_"):
        if len(part) == 4 and part[:2].isdigit() and part[2:].isalpha():
            return part
    parts = path.stem.split("_")
    return parts[1] if len(parts) > 1 else None
