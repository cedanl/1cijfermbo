"""CLI voor eencijfermbo: ingest, transform, pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eencijfermbo",
        description="ETL-tool voor DUO MBO-bestanden (H15/H16/H17) naar CSV/Parquet",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    sub = parser.add_subparsers(dest="commando", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Lees één DUO MBO-bestand in")
    p_ingest.add_argument("bestand", type=Path, help="Pad naar H15/H16/H17 bestand")
    p_ingest.add_argument("--type", choices=["h15", "h16", "h17"], help="Bestandstype (optioneel, wordt anders geraden)")
    p_ingest.add_argument("--output", "-o", type=Path, default=None, help="Uitvoerbestand (.csv of .parquet)")

    # pipeline
    p_pipe = sub.add_parser("pipeline", help="Verwerk alle bestanden in een map")
    p_pipe.add_argument("--input", "-i", type=Path, required=True, help="Invoermap met DUO-bestanden")
    p_pipe.add_argument("--output", "-o", type=Path, required=True, help="Uitvoermap voor CSV/Parquet")
    p_pipe.add_argument("--formaat", choices=["csv", "parquet"], default="csv", help="Uitvoerformaat (standaard: csv)")
    p_pipe.add_argument("--geen-transform", action="store_true", help="Sla afleidingen (cohortjaar, dropout) over")

    return parser


def _cmd_ingest(args: argparse.Namespace) -> None:
    from eencijfermbo.core.ingest import parse_grondslag_ip, parse_ro, parse_tbgi

    parsers = {"h15": parse_ro, "h16": parse_tbgi, "h17": parse_grondslag_ip}

    if args.type:
        df = parsers[args.type](args.bestand)
    else:
        from eencijfermbo.core.pipeline import ingest_bestand
        df = ingest_bestand(args.bestand)

    console.print(df)

    if args.output:
        if args.output.suffix == ".parquet":
            df.write_parquet(args.output)
        else:
            df.write_csv(args.output)
        console.print(f"[green]Opgeslagen:[/green] {args.output}")


def _cmd_pipeline(args: argparse.Namespace) -> None:
    from eencijfermbo.core.pipeline import run_pipeline

    run_pipeline(
        args.input,
        args.output,
        transformeer=not args.geen_transform,
        formaat=args.formaat,
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.commando == "ingest":
            _cmd_ingest(args)
        elif args.commando == "pipeline":
            _cmd_pipeline(args)
    except Exception as exc:
        console.print(f"[bold red]Fout:[/bold red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
