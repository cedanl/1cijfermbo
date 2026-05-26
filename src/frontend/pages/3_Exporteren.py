"""Stap 3: Exporteer verwerkte data als CSV of Parquet."""

from __future__ import annotations

import io

import streamlit as st

st.set_page_config(page_title="Exporteren — 1CijferMBO", layout="wide")
st.title("Stap 3: Exporteren")

bron = st.session_state.get("getransformeerd") or st.session_state.get("ingelezen")
if not bron:
    st.warning("Geen data beschikbaar. Doorloop eerst stappen 1 en 2.")
    st.stop()

naam = st.selectbox("Bestand", list(bron.keys()))
df = bron[naam]
formaat = st.radio("Uitvoerformaat", ["CSV", "Parquet"], horizontal=True)

st.subheader("Preview")
st.dataframe(df.head(10), use_container_width=True)
st.caption(f"{len(df)} rijen × {len(df.columns)} kolommen")

if formaat == "CSV":
    data = df.write_csv().encode("utf-8")
    bestandsnaam = naam.rsplit(".", 1)[0] + "_verwerkt.csv"
    mime = "text/csv"
else:
    buf = io.BytesIO()
    df.write_parquet(buf)
    data = buf.getvalue()
    bestandsnaam = naam.rsplit(".", 1)[0] + "_verwerkt.parquet"
    mime = "application/octet-stream"

st.download_button(
    label=f"Download {formaat}",
    data=data,
    file_name=bestandsnaam,
    mime=mime,
)
