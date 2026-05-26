# 1cijfermbo

## Overview
ETL-tool voor DUO MBO-bestanden (H15/H16/H17) naar schone CSV/Parquet. Package `eencijfermbo` met CLI en Streamlit UI.

## Standards
Follow CEDA technical standards: https://github.com/cedanl/.github/tree/main/standards/README.md

## Tech Stack
Python 3.13, Polars, lxml, Rich, Streamlit (optioneel).

## Project Structure
```
src/eencijfermbo/
├── core/
│   ├── ingest.py      # parse_ro (H15), parse_tbgi (H16), parse_grondslag_ip (H17)
│   ├── transform.py   # derive_cohortjaar, derive_leeftijd, derive_dropout, etc.
│   └── pipeline.py    # run_pipeline() + CLI-helpers
├── cli.py             # eencijfermbo CLI entry point
└── metadata/
src/frontend/          # Streamlit app (3 pagina's)
tests/
data/
├── 01-raw/demo/       # H15/H16/H17 demo-bestanden
├── 02-prepared/demo/
└── 03-output/demo/
```

## How to Run
```bash
uv sync
uv run pytest
uv run eencijfermbo pipeline --input data/01-raw/demo --output data/02-prepared/demo
uv sync --extra frontend && uv run streamlit run src/frontend/main.py
```

## Data
Demo-bestanden in `data/01-raw/demo/`: geanonimiseerde H15/H16/H17 voorbeelden van Aventus en Curio (10 studenten per bestand). Productiedata nooit committen.
