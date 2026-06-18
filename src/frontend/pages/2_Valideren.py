"""Stap 2: Valideer ingelezen data en bekijk afleidingen."""

from __future__ import annotations

import polars as pl
import streamlit as st

from eencijfermbo.core.transform import (
    derive_cohortjaar,
    derive_dropout,
    derive_leeftijd,
    derive_vooropleiding_categorie,
)

st.set_page_config(page_title="Valideren — 1CijferMBO", layout="wide")
st.title("Stap 2: Valideren")

if "ingelezen" not in st.session_state:
    st.warning("Geen data geladen. Ga eerst naar **Inladen**.")
    st.stop()

ingelezen: dict[str, pl.DataFrame] = st.session_state["ingelezen"]
naam = st.selectbox("Bestand", list(ingelezen.keys()))
df = ingelezen[naam]

st.subheader("Ruwe data")
col1, col2, col3 = st.columns(3)
col1.metric("Studenten", len(df))
col2.metric("Kolommen", len(df.columns))
col3.metric("Met diploma", int(df["heeft_diploma"].sum()) if "heeft_diploma" in df.schema else "—")

st.dataframe(df, use_container_width=True)

st.subheader("Ontbrekende waarden")
null_counts = {c: df[c].null_count() for c in df.columns if df[c].null_count() > 0}
if null_counts:
    st.dataframe(
        pl.DataFrame({"kolom": list(null_counts.keys()), "nulls": list(null_counts.values())}),
        use_container_width=True,
    )
else:
    st.success("Geen ontbrekende waarden.")

st.subheader("Afleidingen (preview)")
transformeer = st.checkbox(
    "Pas afleidingen toe (cohortjaar, leeftijd, dropout, vooropleiding)", value=True
)
if transformeer:
    try:
        df_t = derive_cohortjaar(df)
        df_t = derive_leeftijd(df_t)
        df_t = derive_dropout(df_t)
        df_t = derive_vooropleiding_categorie(df_t)
        st.dataframe(df_t.head(20), use_container_width=True)
        st.session_state["getransformeerd"] = {naam: df_t}
    except Exception as exc:
        st.error(f"Fout bij afleidingen: {exc}")
