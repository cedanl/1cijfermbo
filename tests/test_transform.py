"""Tests voor transform-afleidingen."""

from datetime import date

import polars as pl
import pytest

from eencijfermbo.core.transform import (
    derive_cohortjaar,
    derive_dropout,
    derive_leeftijd,
    derive_vooropleiding_categorie,
)


def _basis_df() -> pl.DataFrame:
    return pl.DataFrame({
        "bsn": ["111", "222", "333"],
        "brin": ["27DV", "27DV", "27DV"],
        "inschrijving_start": [date(2023, 9, 1), date(2022, 9, 1), date(2021, 9, 1)],
        "heeft_diploma": [False, True, False],
        "uitschrijving_reden": ["05", None, ""],
        "vorig_onderwijs_niveau": ["HAVO", "VWO", "MBO niveau 3"],
        "leeftijd": [18, 19, 22],
        "geboortedatum": [None, None, None],
    })


def test_derive_cohortjaar() -> None:
    df = derive_cohortjaar(_basis_df())
    assert "cohortjaar" in df.columns
    assert df["cohortjaar"].to_list() == [2023, 2022, 2021]


def test_derive_dropout() -> None:
    df = derive_dropout(_basis_df())
    assert "dropout" in df.columns
    # student 1: uitgeschreven zonder diploma → dropout
    # student 2: heeft diploma → geen dropout
    # student 3: uitschrijving_reden leeg → geen dropout
    assert df["dropout"].to_list() == [True, False, False]


def test_derive_leeftijd_via_leeftijd_kolom() -> None:
    df = derive_leeftijd(_basis_df())
    assert "leeftijd_afgeleid" in df.columns
    assert df["leeftijd_afgeleid"].to_list() == [18, 19, 22]


def test_derive_vooropleiding_categorie() -> None:
    df = derive_vooropleiding_categorie(_basis_df())
    assert "vooropleiding_categorie" in df.columns
    cats = df["vooropleiding_categorie"].to_list()
    assert cats[0] == "HAVO"
    assert cats[1] == "VWO"
    assert cats[2] == "MBO"


def test_derive_vooropleiding_onbekend() -> None:
    df = pl.DataFrame({"vorig_onderwijs_niveau": [None, ""]})
    df = derive_vooropleiding_categorie(df)
    assert all(v == "Onbekend" for v in df["vooropleiding_categorie"].to_list())
