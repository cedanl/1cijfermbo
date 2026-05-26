# 1CijferMBO

ETL-tool voor het omzetten van DUO MBO-leveringen (H15/H16/H17) naar schone CSV- of Parquet-bestanden.

## Ondersteunde bestandstypen

| Type | Naam | Formaat |
|------|------|---------|
| H15 | Registratie Overzicht (RO) | Pipe/puntkomma-gescheiden records |
| H16 | TBG-i | XML |
| H17 | Afslag register-levering IP | Puntkomma-gescheiden records |

## Installatie

```bash
pip install eencijfermbo
```

Of met uv:

```bash
uv add eencijfermbo
```

Voor de Streamlit UI:

```bash
uv add "eencijfermbo[frontend]"
```

## Gebruik

### CLI

```bash
eencijfermbo pipeline --input data/01-raw/ --output data/02-prepared/
eencijfermbo ingest RO_27DV_20240731_20260324.csv
eencijfermbo pipeline --input data/ --output output/ --formaat parquet
```

### Streamlit UI

```bash
uv run streamlit run src/frontend/main.py
```

### Python

```python
from eencijfermbo.core.ingest import parse_ro, parse_tbgi, parse_grondslag_ip
from eencijfermbo.core.pipeline import run_pipeline

df = parse_ro("data/RO_27DV_20240731_20260324.csv")
run_pipeline(input_dir=Path("data/01-raw"), output_dir=Path("data/02-prepared"))
```

## Ontwikkeling

```bash
git clone https://github.com/cedanl/1cijfermbo.git && cd 1cijfermbo
uv sync --extra frontend
uv run pytest
```

Met devcontainer: open de repo in VS Code en kies "Reopen in Container".

## Licentie

EUPL-1.2 — zie [LICENSE](LICENSE)
