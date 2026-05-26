"""Derivatiefuncties voor afleidbare variabelen uit DUO MBO bestandsformaten.

Elke functie accepteert een genormaliseerde student-DataFrame (output van parse_*)
en geeft een Polars Expression of Series terug.
"""

from __future__ import annotations

import polars as pl

_NIVEAU_MAP: dict[str, str] = {
    "VWO": "VWO",
    "HAVO": "HAVO",
    "VMBO": "VMBO/MAVO",
    "MAVO": "VMBO/MAVO",
    "VBO": "VMBO/MAVO",
}


def derive_cohortjaar(df: pl.DataFrame) -> pl.DataFrame:
    """Voeg cohortjaar toe als jaar van de eerste inschrijving."""
    return df.with_columns(pl.col("inschrijving_start").dt.year().alias("cohortjaar"))


def derive_leeftijd(df: pl.DataFrame) -> pl.DataFrame:
    """Voeg leeftijd_afgeleid toe op peildatum 1 oktober van het cohortjaar.

    H15: berekend vanuit geboortedatum (PER-record).
    H16/H17: direct beschikbaar als integer (LeeftijdOpEenAugustusStudiejaar / PER[2]).
    """
    if "geboortedatum" in df.schema and df["geboortedatum"].is_not_null().any():
        df = df.with_columns(
            pl.date(
                pl.col("inschrijving_start").dt.year(),
                pl.lit(10),
                pl.lit(1),
            ).alias("_peildatum")
        )
        df = df.with_columns(
            (
                (pl.col("_peildatum") - pl.col("geboortedatum")).dt.total_days() / 365.25
            )
            .round(0)
            .cast(pl.Int64)
            .alias("leeftijd_afgeleid")
        ).drop("_peildatum")
    elif "leeftijd" in df.schema:
        df = df.with_columns(pl.col("leeftijd").alias("leeftijd_afgeleid"))
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Int64).alias("leeftijd_afgeleid"))
    return df


def derive_dropout(df: pl.DataFrame) -> pl.DataFrame:
    """Voeg dropout-kolom toe: uitgeschreven zonder diploma.

    Uitgeschreven = uitschrijving_datum is ingevuld (H15/H16/H17) OF
    uitschrijving_reden is ingevuld (H15/H17). H16 heeft geen reden-code.
    Beperking: snapshot-levering toont geen herinschrijving elders.
    """
    uitgeschreven = pl.lit(False)
    if "uitschrijving_datum" in df.schema:
        uitgeschreven = uitgeschreven | pl.col("uitschrijving_datum").is_not_null()
    if "uitschrijving_reden" in df.schema:
        uitgeschreven = uitgeschreven | (
            pl.col("uitschrijving_reden").is_not_null()
            & (pl.col("uitschrijving_reden") != "")
        )
    return df.with_columns((uitgeschreven & ~pl.col("heeft_diploma")).alias("dropout"))


def derive_vooropleiding_categorie(df: pl.DataFrame) -> pl.DataFrame:
    """Voeg vooropleiding_categorie toe op basis van vorig_onderwijs_niveau."""
    mapping = pl.DataFrame({
        "vorig_onderwijs_niveau": list(_NIVEAU_MAP.keys()),
        "vooropleiding_categorie": list(_NIVEAU_MAP.values()),
    })

    df = df.join(mapping, on="vorig_onderwijs_niveau", how="left")

    df = df.with_columns(
        pl.when(pl.col("vooropleiding_categorie").is_null())
        .then(
            pl.when(
                pl.col("vorig_onderwijs_niveau").str.contains("MBO|KZDL", literal=False)
            )
            .then(pl.lit("MBO"))
            .when(pl.col("vorig_onderwijs_niveau").str.contains("HBO", literal=False))
            .then(pl.lit("HBO"))
            .when(
                pl.col("vorig_onderwijs_niveau").is_null()
                | (pl.col("vorig_onderwijs_niveau") == "")
            )
            .then(pl.lit("Onbekend"))
            .otherwise(pl.lit("Anders"))
        )
        .otherwise(pl.col("vooropleiding_categorie"))
        .alias("vooropleiding_categorie")
    )
    return df


def derive_opleidingssector(
    df: pl.DataFrame, mapping: dict[str, str] | None = None
) -> pl.DataFrame:
    """Voeg opleidingssector toe op basis van CREBO-opleidingscode.

    Vereist een externe CREBO-sectorMapping (dict van opleidingscode → sector).
    Zonder mapping worden alle waarden als 'Onbekend' geclassificeerd.
    """
    if mapping is None:
        return df.with_columns(pl.lit("Onbekend").alias("opleidingssector"))

    sector_df = pl.DataFrame({
        "opleidingscode": list(mapping.keys()),
        "opleidingssector": list(mapping.values()),
    })
    return df.join(sector_df, on="opleidingscode", how="left").with_columns(
        pl.col("opleidingssector").fill_null("Onbekend")
    )
