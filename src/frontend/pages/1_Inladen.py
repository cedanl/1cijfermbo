"""Stap 1: DUO MBO-bestanden uploaden en inlezen."""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl
import streamlit as st

from eencijfermbo.core.pipeline import detect_bestandstype, ingest_bestand

st.set_page_config(page_title="Inladen — 1CijferMBO", layout="wide")
st.title("Stap 1: Inladen")
st.caption("Upload H15, H16 of H17 DUO MBO-bestanden")

uploaded = st.file_uploader(
    "Selecteer bestand(en)",
    type=["csv", "txt", "xml", "XML"],
    accept_multiple_files=True,
)

if not uploaded:
    st.info("Nog geen bestanden geüpload.")
    st.stop()

resultaten: dict[str, pl.DataFrame] = {}

for file in uploaded:
    with tempfile.NamedTemporaryFile(suffix=Path(file.name).suffix, delete=False) as tmp:
        tmp.write(file.read())
        tmp_path = Path(tmp.name)

    btype = detect_bestandstype(Path(file.name))
    label = btype.upper() if btype else "onbekend"

    with st.expander(f"**{file.name}** — {label}", expanded=True):
        if btype is None:
            st.error(
                f"Kan bestandstype niet bepalen voor `{file.name}`. "
                "Verwacht: RO_*, TBGI_* of GRONDSLAG_IP_*."
            )
            continue
        try:
            df = ingest_bestand(tmp_path, bestandstype=btype)
            resultaten[file.name] = df
            st.success(f"{len(df)} studenten ingelezen, {len(df.columns)} kolommen")
            st.dataframe(df.head(20), use_container_width=True)
        except Exception as exc:
            st.error(f"Fout: {exc}")

if resultaten:
    st.session_state["ingelezen"] = resultaten
    st.success(f"**{len(resultaten)} bestand(en) klaar.** Ga naar Valideren →")
