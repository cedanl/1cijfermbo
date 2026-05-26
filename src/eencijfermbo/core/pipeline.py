"""End-to-end ETL pipeline voor DUO MBO-bestanden."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from rich.console import Console
from rich.table import Table

from eencijfermbo.core.ingest import parse_grondslag_ip, parse_ro, parse_tbgi
from eencijfermbo.core.transform import (
    derive_cohortjaar,
    derive_dropout,
    derive_leeftijd,
    derive_vooropleiding_categorie,
)

console = Console()

_PARSERS = {
    "h15": parse_ro,
    "h16": parse_tbgi,
    "h17": parse_grondslag_ip,
}

_EXTENSIONS = {
    "h15": {".csv", ".txt"},
    "h16": {".xml", ".XML"},
    "h17": {".csv", ".txt"},
}


def detect_bestandstype(path: Path) -> str | None:
    """Detecteer H15/H16/H17 op basis van bestandsnaam en extensie."""
    stem = path.stem.upper()
    if stem.startswith("RO_") or stem.startswith("RO"):
        return "h15"
    if stem.startswith("TBGI"):
        return "h16"
    if stem.startswith("GRONDSLAG_IP"):
        return "h17"
    ext = path.suffix.lower()
    if ext == ".xml":
        return "h16"
    return None


def ingest_bestand(path: Path, bestandstype: str | None = None) -> pl.DataFrame:
    """Parse één DUO MBO-bestand; detecteert type als niet opgegeven."""
    btype = bestandstype or detect_bestandstype(path)
    if btype is None:
        raise ValueError(f"Onbekend bestandstype voor: {path.name}")
    parse_fn = _PARSERS[btype]
    console.print(f"  [cyan]Inlezen[/cyan] {path.name} als {btype.upper()}")
    df = parse_fn(path)
    console.print(f"  → {len(df)} studenten")
    return df


def transform_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Pas standaard afleidingen toe op een genormaliseerde student-DataFrame."""
    df = derive_cohortjaar(df)
    df = derive_leeftijd(df)
    df = derive_dropout(df)
    df = derive_vooropleiding_categorie(df)
    return df


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    *,
    transformeer: bool = True,
    formaat: str = "csv",
) -> dict[str, pl.DataFrame]:
    """Verwerk alle DUO MBO-bestanden in input_dir naar output_dir.

    Args:
        input_dir: Map met H15/H16/H17 bronbestanden.
        output_dir: Map waar CSV/Parquet-bestanden worden opgeslagen.
        transformeer: Of afleidingen (cohortjaar, leeftijd, dropout) worden toegepast.
        formaat: Uitvoerformaat: 'csv' of 'parquet'.

    Returns:
        Dict van bestandsnaam → DataFrame per verwerkt bestand.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    resultaten: dict[str, pl.DataFrame] = {}
    bestanden = [
        p for p in sorted(input_dir.iterdir())
        if p.is_file() and not p.name.startswith(".")
    ]

    if not bestanden:
        console.print(f"[yellow]Geen bestanden gevonden in {input_dir}[/yellow]")
        return resultaten

    console.print(f"\n[bold]Pipeline: {len(bestanden)} bestand(en) in {input_dir}[/bold]\n")

    for pad in bestanden:
        try:
            df = ingest_bestand(pad)
            if transformeer:
                df = transform_dataframe(df)
            uitvoernaam = pad.stem
            _export(df, output_dir / uitvoernaam, formaat)
            resultaten[pad.name] = df
        except Exception as exc:
            console.print(f"  [red]Fout bij {pad.name}: {exc}[/red]")

    _print_samenvatting(resultaten)
    return resultaten


def _export(df: pl.DataFrame, stem: Path, formaat: str) -> None:
    if formaat == "parquet":
        pad = stem.with_suffix(".parquet")
        df.write_parquet(pad)
    else:
        pad = stem.with_suffix(".csv")
        df.write_csv(pad)
    console.print(f"  [green]Opgeslagen[/green] → {pad.name}")


def _print_samenvatting(resultaten: dict[str, pl.DataFrame]) -> None:
    if not resultaten:
        return
    table = Table(title="Samenvatting", show_header=True)
    table.add_column("Bestand")
    table.add_column("Studenten", justify="right")
    table.add_column("Kolommen", justify="right")
    for naam, df in resultaten.items():
        table.add_row(naam, str(len(df)), str(len(df.columns)))
    console.print(table)
