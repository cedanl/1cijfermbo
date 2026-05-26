"""Streamlit hoofdpagina voor eencijfermbo ETL-tool."""

import streamlit as st

st.set_page_config(
    page_title="1CijferMBO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("1CijferMBO")
st.subheader("ETL-tool voor DUO MBO-bestanden")

st.markdown("""
Welkom bij **1CijferMBO** — de tool voor het omzetten van DUO MBO-leveringen
naar schone CSV- of Parquet-bestanden.

### Ondersteunde bestandstypen

| Type | Naam | Formaat |
|------|------|---------|
| H15 | Registratie Overzicht (RO) | Pipe/puntkomma-gescheiden records |
| H16 | TBG-i | XML |
| H17 | Afslag register-levering IP | Puntkomma-gescheiden records |

### Gebruik

Navigeer via het linkermenu:

1. **Inladen** — upload één of meerdere DUO MBO-bestanden
2. **Valideren** — bekijk de ingelezen data en eventuele waarschuwingen
3. **Exporteren** — download als CSV of Parquet

---

*Gebouwd door [CEDA / Npuls](https://github.com/cedanl)*
""")

with st.sidebar:
    st.markdown("### Over")
    st.markdown("Versie `0.1.0`")
    st.markdown("[GitHub](https://github.com/cedanl/1cijfermbo)")
